import sys
import os
import asyncio

sys.path.insert(0, '/a0')
from initialize import initialize_agent
from agent import AgentContext, AgentContextType, UserMessage

async def main():
    msg_text = sys.argv[1] if len(sys.argv) > 1 else "E2E Test Message"
    print("--- TRIGGER START ---")
    config = initialize_agent()
    # Force profile if needed, but default is fine
    context = AgentContext(config=config, type=AgentContextType.USER)
    AgentContext.use(context.id)
    
    msg = UserMessage(msg_text, None)
    task = context.communicate(msg)
    
    try:
        await asyncio.wait_for(task.result(), timeout=60)
        for history_msg in reversed(context.history):
            role = getattr(history_msg, 'role', None) or history_msg.get('role', '') if isinstance(history_msg, dict) else None
            content = getattr(history_msg, 'content', None) or history_msg.get('content', '') if isinstance(history_msg, dict) else None
            
            if role == 'assistant':
                # The LLM stub's echo output
                print(f"ASSISTANT_RESPONSE: {content}")
                break
    except Exception as e:
        print(f"Agent loop finished or timeout: {e}")

    print("--- TRIGGER END ---")

if __name__ == "__main__":
    asyncio.run(main())
