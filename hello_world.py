"""Antigravity SDK 連通性驗證 — 確認能程式化驅動 Gemini agent。"""
import asyncio, os, sys
from dotenv import load_dotenv
from google.antigravity import Agent, LocalAgentConfig

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


async def main():
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        sys.exit("缺 GEMINI_API_KEY，請先設定（見 README）")

    async with Agent(LocalAgentConfig()) as agent:
        # 1. 基本問答
        r = await agent.chat("用繁體中文一句話回答：你是哪個模型？")
        print("【回答】", await r.text())

        # 2. 串流思考過程（驗證 thoughts 通道）
        r2 = await agent.chat("17 * 23 等於多少？只回數字。")
        thoughts = "".join([t async for t in r2.thoughts])
        print("【思考】", (thoughts[:200] + "…") if len(thoughts) > 200 else thoughts or "(無)")
        print("【答案】", (await r2.text()).strip())


asyncio.run(main())
