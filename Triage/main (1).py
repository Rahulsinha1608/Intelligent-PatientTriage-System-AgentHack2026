from datetime import (
    datetime,
    timezone
)
from langchain_core.messages import (
    HumanMessage,
    SystemMessage
)
from pydantic import (
    BaseModel,
    Field
)
from pydantic import (
    ConfigDict
)
from typing import (
    Sequence
)
from uipath.agent.models.agent import (
    AgentContextResourceConfig
)
from uipath.agent.react import (
    AGENT_SYSTEM_PROMPT_TEMPLATE
)
from uipath_langchain.agent.react import (
    create_agent
)
from uipath_langchain.agent.tools.context_tool import (
    handle_semantic_search
)
from uipath_langchain.chat.chat_model_factory import (
    get_chat_model
)
from utils import (
    interpolate_legacy_message
)



# LLM Model Configuration
llm = get_chat_model(
    model='gpt-5.4',
    temperature=0.0,
    max_tokens=128000,
    agenthub_config="agentsruntime",
)
    
# Context Tool guide
guide_config = AgentContextResourceConfig(
    name='Guide',
    description='',
    resource_type='context',
    folder_path='solution_folder',
    index_name='Guide',
    settings={'resultCount': 3, 'retrievalMode': 'Semantic', 'threshold': 0.0, 'query': {'description': 'The query for the Semantic strategy.', 'variant': 'dynamic'}, 'folderPathPrefix': {'variant': 'static'}, 'fileExtension': {'value': 'All'}},
    is_enabled=True
)
guide_tool = handle_semantic_search('guide', guide_config)


# Collect all tools
tools = []
tools.append(guide_tool)


# Input/Output Models
class AgentInput(BaseModel):
    model_config = ConfigDict(extra='allow')
    Name: str
    Age: float
    Gender: str
    Symptoms: str
    Medication: str | None = None
    Duration: str
    Email: str


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra='allow')
    Severity: str = Field(..., description="Output content")
    Issue: str
    NextAction: str

# Agent Messages Function
def create_messages(state: AgentInput) -> Sequence[SystemMessage | HumanMessage]:
    # Extract values safely from state
    Age = getattr(state, 'Age', '')
    Duration = getattr(state, 'Duration', '')
    Email = getattr(state, 'Email', '')
    Gender = getattr(state, 'Gender', '')
    Medication = getattr(state, 'Medication', '')
    Name = getattr(state, 'Name', '')
    Symptoms = getattr(state, 'Symptoms', '')

    # Apply system prompt template
    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    system_prompt_content = """You are an AI Medical Symptom Triage Agent.

You have access to a Context in the form of a medical reference table. Each row contains:

- Condition
- Common Symptoms
- Severity
- Recommended Specialist
- Recommended Action
- Keywords

Your job is to analyze the patient's information by referring ONLY to this Context.

Instructions:

1. Read the patient's symptoms carefully.
2. Compare the patient's symptoms with the **Keywords** and **Common Symptoms** in the Context.
3. Find the best matching row in the Context.
4. Use ONLY the information from that matching row.
5. Generate the following outputs:

   • Severity
     - Return the Severity exactly as mentioned in the matched Context row.

   • Reason
     - Explain why the case matched that row by mentioning the matching symptoms or keywords from the patient's input.

   • Recommendation
     - Return the Recommended Specialist from the matched Context row.

   • Next Action
     - Return the Recommended Action from the matched Context row.

6. If multiple rows match, choose the one with the highest severity.

   Severity Priority:
   Emergency > High > Medium > Normal

7. If no suitable match is found, return:

Severity: Unknown

Reason:
The patient's symptoms do not sufficiently match any condition in the provided Context.

Recommendation:
Consult a General Physician for further evaluation.

Next Action:
Seek professional medical advice if symptoms persist or worsen.

8. Do not diagnose diseases or provide medical advice beyond what is available in the Context.

9. Do not use external medical knowledge.

10. Keep the response short, professional, and easy to understand.

Output Format:

Severity:
Reason:
Recommendation:
Next Action:
"""
    system_prompt_content = interpolate_legacy_message(system_prompt_content, state.model_dump())
    enhanced_system_prompt = (
        AGENT_SYSTEM_PROMPT_TEMPLATE
        .replace('{{systemPrompt}}', system_prompt_content)
        .replace('{{currentDate}}', current_date)
        .replace('{{agentName}}', 'Mr Assistant')
    )

    return [
        SystemMessage(content=enhanced_system_prompt),
        HumanMessage(content=interpolate_legacy_message("""Refer to the provided Context and analyze the following patient details.

Patient Information

Name: {{Name}}

Email : {{Email}}

Age: {{Age}}

Gender: {{Gender}}

Symptoms: {{Symptoms}}

Current Medication: {{Medication}}

Duration of Symptoms: {{Duration}}

Instructions:
""", state.model_dump())),
    ]

# Create agent graph
graph = create_agent(model=llm, messages=create_messages, tools=tools, input_schema=AgentInput, output_schema=AgentOutput)