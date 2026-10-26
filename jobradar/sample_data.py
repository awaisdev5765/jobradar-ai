from .core import Opportunity


def sample_opportunities() -> list[Opportunity]:
    return [
        Opportunity("Python Computer Vision Engineer", "Northstar Robotics", "Remote · Europe", "Build OpenCV and Python inspection pipelines using ONNX and computer vision.", "https://example.com/jobs/vision", "Company careers", 65000, True, ["Python", "OpenCV", "ONNX"]),
        Opportunity("Applied AI Developer", "Atlas Health", "Remote · Worldwide", "Develop privacy-first Python AI tools and production APIs.", "https://example.com/jobs/ai", "Remote feed", 52000, True, ["Python", "FastAPI", "AI"]),
        Opportunity("Junior Backend Engineer", "Harbour Labs", "London · Hybrid", "Python backend role with two office days each week.", "https://example.com/jobs/backend", "Startup board", 42000, False, ["Python", "PostgreSQL"]),
        Opportunity("AI Automation Expert", "Instant Wealth Ltd", "Remote", "Telegram only. Pay a registration fee before onboarding and receive crypto payment.", "https://example.com/jobs/risky", "Open web", 90000, True, ["AI", "Automation"]),
        Opportunity("OpenCV Contract Developer", "FieldMetric", "Remote · UK/EU", "Six-month contract building edge vision software in Python.", "https://example.com/jobs/contract", "Contract feed", 70000, True, ["Python", "OpenCV", "Edge AI"]),
    ]
