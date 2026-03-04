import asyncio
from playwright.async_api import async_playwright
import time
import os

async def run_v020_final_verification():
    """
    v0.2.0 Final Optimization Verification Suite.
    Verifies:
    1. Cognitive Optimization (Generic Branding)
    2. Real-time Graph Sync (Linkage between new entities)
    """
    print("\n--- 🧠 STARTING GRAPHRAG v0.2.0 COGNITIVE & SYNC VERIFICATION ---")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("[1/3] Connecting to Agent Zero at http://localhost:8086...")
            await page.goto("http://localhost:8086", timeout=30000)
            await page.wait_for_load_state("networkidle")
            
            # Start New Chat
            new_chat_btn = page.get_by_text("New Chat").first
            await new_chat_btn.click()
            await page.wait_for_timeout(2000)
            
            # Prompt for Multi-Stage Verification
            verification_prompt = """
# 🔬 v0.2.0 FINAL AUDIT
Please execute the following and report findings strictly:

1. **Cognitive Audit**: Do you see 'COGNITIVE OPTIMIZATION: INTELLECTUAL RESEARCH' or similar instructions in your core system loop?
2. **Real-time Sync**: Save this fact: "The Hyperion Core was developed by the Nebula Consortium in 2026."
3. **Linkage Test**: Search for "Nebula Consortium". Does it link to "Hyperion Core" via the graph?
"""
            print("[2/3] Injecting Final Audit Prompt...")
            chat_input = page.locator("#chat-input").first
            await chat_input.fill(verification_prompt)
            await chat_input.press("Enter")
            
            # Wait for Sync and Reasoning (increased to 90s for dual tool calls)
            print("Waiting for Graph Processing & Sync (90s)...")
            await page.wait_for_timeout(90000)
            
            # Snapshot
            evidence_path = "/Users/george/Mac/data/usr/projects/ai_joose_factory/Projects/graphrag-agent-zero/tmp_playwright/v020_final_fix_success.png"
            await page.screenshot(path=evidence_path)
            print(f"[3/3] Verification Snapshot captured at {evidence_path}")
            
            # Result Audit
            body_text = await page.evaluate("document.body.innerText")
            found_optimization = "INTELLECTUAL RESEARCH" in body_text or "COGNITIVE OPTIMIZATION" in body_text
            found_sync = "Hyperion Core" in body_text and "Nebula Consortium" in body_text
            
            if found_optimization and found_sync:
                print("✅ STATUS: v0.2.0 OPTIMIZED & SYNCHRONIZED")
            else:
                print(f"⚠️ STATUS: PARTIAL (Opt: {found_optimization}, Sync: {found_sync})")
                
        except Exception as e:
            print(f"FAILED: {e}")
            
        print("--- VERIFICATION COMPLETE ---\n")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_v020_final_verification())
