import os
import logging
from typing import TypedDict, Optional
from backend.models.user_model import User
from langchain_core.messages import SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import StateGraph, END

from backend.models.vectordb_models import PineconeConfig
from backend.services.prompts.dm_workflow_prompts import *
import json
from backend.helpers import get_env_value
from backend.models.ai_processing_models import MessageRecommendationContext, MessageAnalysis
from backend.services.rag_service.pinecone import PineconeDB
from backend.services.vector_db_service import VectorDbService

logger = logging.getLogger(__name__)


class DMModeratorAgentState(TypedDict):
    conversation_history: list[dict]
    conversation_history_query: str
    latest_message: str
    clarity_status: str
    retrieved_context: Optional[str]
    message_type: Optional[str]  # TEXT, SELF_IG_REEL, etc.
    category: Optional[str]  # Product Inquiry, General Inquiry, etc.
    suggested_message_reply: Optional[str]
    formatted_suggested_dm: Optional[str]


os.environ["AZURE_OPENAI_API_KEY"] = get_env_value('AZURE_OPENAI_API_KEY')
os.environ["AZURE_OPENAI_ENDPOINT"] = get_env_value('AZURE_OPENAI_ENDPOINT')
OPENAI_API_VERSION = get_env_value('OPENAI_API_VERSION')
AZURE_MODEL_NAME = get_env_value('AZURE_MODEL_NAME')


class DMAIService:
    def __init__(self, vector_db_service: VectorDbService):
        self.model = AzureChatOpenAI(
            azure_deployment=AZURE_MODEL_NAME,
            api_version=OPENAI_API_VERSION,
            temperature=0,
            presence_penalty=0,
            frequency_penalty=0
        )
        self.graph = self._create_graph()
        self.vectordb_service = vector_db_service

    def _create_graph(self):
        builder = StateGraph(DMModeratorAgentState)

        builder.add_node("classify_conversation", self.conversation_classification_node)
        builder.add_node("validate_context", self.context_validation_node)
        builder.add_node("generate_reply", self.reply_generation_node)
        builder.add_node("generate_user_friendly_dm", self.generate_user_friendly_dm)
        builder.add_node("grade_factual_consistency", self.grade_factual_consistency_node)

        builder.add_edge("classify_conversation", "validate_context")
        builder.add_edge("validate_context","generate_reply")
        builder.add_edge("generate_reply", "generate_user_friendly_dm")
        builder.add_edge("generate_user_friendly_dm", "grade_factual_consistency")
        builder.add_edge("grade_factual_consistency", END)

        # Set the entry point and compile
        builder.set_entry_point("classify_conversation")
        return builder.compile()


    async def context_validation_node(self, state: DMModeratorAgentState):
        """
        Validate if the conversation query is clear and sufficient to respond appropriately.
        Uses the DM_CONTEXT_VALIDATION_PROMPT to detect missing context.
        """

        logger.debug("Running context validation")
        context = await self.vectordb_service.retrieve(query=state.get('conversation_history_query'))
        filtered_docs = [
            doc for doc, score in context if score >= 0.4
        ]

        # 3. decide what to keep in the state
        if filtered_docs:
            # join or otherwise serialize the docs for downstream use
            context_text = "\n\n".join(d.page_content for d in filtered_docs)
        else:
            context_text = "No context available"
        prompt = DM_CONTEXT_VALIDATION_PROMPT.format(
            conversation_history_query=state.get('conversation_history_query'),
            conversation_history=json.dumps(state.get('conversation_history', []), indent=2),
            context=context
        )
        messages = [SystemMessage(content=prompt)]

        response = await self.model.ainvoke(messages)
        json_response = response.content.strip()
        logger.debug(f"Raw response from context validation: {json_response}")

        try:
            # Clean the response for valid JSON parsing
            cleaned_response = json_response.strip("```").replace("json\n", "").strip()
            context_validation_result = json.loads(cleaned_response)
            context_clarity_status = context_validation_result.get("is_context_miss", "").lower()

            return {
                "clarity_status": context_clarity_status,
                "retrieved_context": context_text
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {json_response}, Error: {e}")
            raise ValueError(f"Invalid JSON response from AI: {json_response}")

    async def conversation_classification_node(self, state: DMModeratorAgentState):
        """Classify the conversation type and assign priority."""
        logger.debug("conversation_classification_node")

        prompt = DM_CONVERSATION_CLASSIFIER_PROMPT.format(
            conversation_history=json.dumps(state['conversation_history'], indent=2),
            latest_message=state.get('latest_message')
        )
        messages = [SystemMessage(content=prompt)]
        response = await self.model.ainvoke(messages)
        json_response = response.content.strip()
        logger.debug(f"Raw response from classifier: {json_response}")

        # Parse JSON output
        try:
            cleaned_response = json_response.strip("```").replace("json\n", "").strip()
            classification_json = json.loads(cleaned_response)
            category = classification_json.get("category")
            conversation_history_query = classification_json.get("conversation_history_query")

            return {"category": category, "conversation_history_query": conversation_history_query}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {json_response}, Error: {e}")
            raise ValueError(f"Invalid JSON classification output: {json_response}")


    async def reply_generation_node(self, state: DMModeratorAgentState):
        """Generate a reply based on the DM type and context."""
        logger.debug("reply_generation_node")

        prompt = DM_CONVERSATION_REPLY_GENERATOR_PROMPT.format(
            conversation_history=json.dumps(state['conversation_history'], indent=2),
            retrieved_context=state.get('retrieved_context'),
            conversation_history_query=state.get('conversation_history_query'),
        )
        messages = [SystemMessage(content=prompt)]
        response = await self.model.ainvoke(messages)
        suggested_message_reply = response.content.strip()
        logger.debug(f"Generated Reply: {suggested_message_reply}")

        return {
            "suggested_message_reply": suggested_message_reply,
        }

    async def generate_user_friendly_dm(self, state: DMModeratorAgentState):
        logger.debug("generate_user_friendly_dm")
        prompt = GENERATE_READABLE_DM_FORMAT.format(
            suggested_message_reply=state.get('suggested_message_reply'),
            username=state.get('username')
        )
        messages = [SystemMessage(content=prompt)]
        response = await self.model.ainvoke(messages)
        response_text = response.content.strip()

        return {
            'formatted_suggested_dm': response_text
        }

    async def grade_factual_consistency_node(self, state: DMModeratorAgentState):
        """
        Grade the factual consistency of the generated reply.
        Uses the DM_FACTUAL_CONSISTENCY_PROMPT to validate the response.
        """
        # Prepare the prompt
        prompt = DM_FACTUAL_CONSISTENCY_PROMPT.format(
            suggested_message_reply=state['suggested_message_reply'],
            retrieved_context=state.get('retrieved_context'),
            conversation_history=json.dumps(state['conversation_history'], indent=2)
        )

        messages = [SystemMessage(content=prompt)]
        # Invoke the AI model
        response = await self.model.ainvoke(messages)
        factual_consistency_response = response.content.strip()
        logger.debug(f"Factual Consistency Grading Response: {factual_consistency_response}")

        try:
            cleaned_response = factual_consistency_response.strip("```").replace("json\n", "").strip()
            response_json = json.loads(cleaned_response)

            # Extract factual consistency result
            factual_consistency_status = response_json.get("factual_consistency", "").lower()
            if factual_consistency_status == "yes":
                factual_consistency = True
                factual_inconsistency_reason = None
            elif factual_consistency_status == "no":
                factual_consistency = False
                factual_inconsistency_reason = response_json.get("reason", "No reason provided.")
            else:
                logger.error(f"Unexpected value for 'factual_consistency': {factual_consistency_status}")
                raise ValueError(f"Unexpected 'factual_consistency' value: {factual_consistency_status}")
            return {
                "factual_consistency": {
                    "status": factual_consistency,
                    "reason": factual_inconsistency_reason
                }
            }
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response for factual consistency: {factual_consistency_response}")
            raise ValueError(f"Invalid JSON response: {factual_consistency_response}")


    async def analyse_dm_with_ai(self, message_context: MessageRecommendationContext) -> MessageAnalysis:
        """Analyze a DM with AI to classify and suggest a reply."""
        state = {
            "username": message_context.user.user_name,
            "conversation_history": message_context.enriched_messages,
        }

        try:
            app = self.graph
            image_data = app.get_graph().draw_mermaid_png()
            with open("diagram.png", "wb") as f:
                f.write(image_data)

            import os
            os.system("diagram.png")  # For Windows

        except Exception as e:
            logger.error(f"An error occurred: {e}")

        # Run the State Graph
        result = await self.graph.ainvoke(state)
        logger.debug(f"Message Type is : {result.get('message_type')}")


        return MessageAnalysis(
            message_category=result.get('category'),
            suggested_message_reply=result.get('suggested_message_reply'),
            conversation_summary=result.get('conversation_history_query'),
            factual_consistency=result.get('clarity_status')
        )


if __name__ == '__main__':
    import asyncio
    pinecone_config: PineconeConfig = PineconeConfig(
        base_url='https://sarique-test-n4991xo.svc.aped-4627-b74a.pinecone.io',
        api_key='pcsk_5WohRM_EncoaGWkcYDnHno1FymNXXiKwcKe9c9JRBHUDk2M7gAMRHcxuMYaX2Vuzx2mnML'
    )
    pinecone_db = PineconeDB(config=pinecone_config)
    vector_db_service = VectorDbService(vector_db=pinecone_db)
    dmai_service = DMAIService(vector_db_service=vector_db_service)

    message_context: MessageRecommendationContext = MessageRecommendationContext(
        enriched_messages=[{"text": "hello there"}],
        user=User(
            user_name='sarique',
            user_email='shaarik.aslam@gmail.com',
            password='shaadikA@123'
        )
    )

    asyncio.run(dmai_service.analyse_dm_with_ai(message_context=message_context))