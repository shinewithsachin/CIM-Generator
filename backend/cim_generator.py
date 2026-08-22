"""
CIM Generator — one method per section, each with a detailed expert prompt.
All financial calculations are explicitly instructed for correctness.
"""
import json
import re
from typing import Any, Dict, List, Optional

from rag_service import RAGService
from llm.gateway import GatewayMessage, LLMGateway, LLMGenerateRequest

# ─────────────────────────────────────────────
# LLM Gateway
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# Shared prompt helpers
# ─────────────────────────────────────────────

FINANCIAL_CALC_RULES = """
FINANCIAL CALCULATION RULES (follow strictly):
- Revenue Growth Rate (YoY) = ((Current Year - Previous Year) / Previous Year) × 100  [round to 1 decimal]
- CAGR = (((End Value / Start Value) ^ (1 / n)) - 1) × 100  where n = number of years  [round to 1 decimal]
- Gross Margin (%) = ((Revenue - COGS) / Revenue) × 100
- EBITDA Margin (%) = (EBITDA / Revenue) × 100
- Net Margin (%) = (Net Profit / Revenue) × 100
- EV/EBITDA = Enterprise Value / EBITDA
- P/E Ratio = Market Price per Share / EPS
- Debt/Equity = Total Debt / Total Equity
- Current Ratio = Current Assets / Current Liabilities
- Always show the formula used and intermediate values before giving the final answer.
- Maintain consistent currency units throughout. If amounts are in millions, label as "₹ Mn" or "$ Mn" etc.
- For projections, state the growth assumption used and calculate each year step by step.
"""

CHART_INSTRUCTION = """
At the END of your response, include a JSON block for any charts needed, in this exact format:
```chart_data
[
  {
    "id": "unique_id",
    "type": "bar|line|pie|donut|waterfall|area",
    "title": "Chart Title",
    "x_label": "X-axis label",
    "y_label": "Y-axis label",
    "labels": ["Label1", "Label2", ...],
    "datasets": [
      {"label": "Series Name", "data": [v1, v2, ...], "color": "#2563EB"}
    ]
  }
]
```
Use professional colors: #2563EB (blue), #10B981 (green), #F59E0B (amber), #EF4444 (red), #8B5CF6 (purple), #06B6D4 (cyan).
"""

SYSTEM_PROMPT = """You are an expert investment banker and M&A advisor with 20+ years of experience
drafting Confidential Information Memoranda (CIMs) for sell-side mandates.
Your CIMs are detailed, persuasive, analytically rigorous, and professionally formatted.
Write in third-person, past-and-present tense, in the tone of a bulge-bracket investment bank.
Use specific numbers, metrics, and data points wherever available.
Do not make up data — if data is not in the context, state "data not available in provided documents"
but still write comprehensive qualitative analysis based on industry best practices.
"""


# ─────────────────────────────────────────────
# Section Prompts
# ─────────────────────────────────────────────

SECTION_PROMPTS = {

"executive_summary": """
Write a comprehensive EXECUTIVE SUMMARY for a Confidential Information Memorandum.

This is the most important section — it must be compelling, concise (but thorough),
and make a strong first impression on potential investors/acquirers.

Include ALL of the following sub-sections with detailed content:

## 1. Transaction Overview
- Company name, industry, and brief description
- Nature of the transaction (sale, investment, fundraise, acquisition)
- Transaction size / funding sought
- Instrument type (equity, debt, convertible notes, etc.)
- Advisor / investment bank name

## 2. Company Snapshot
- Year of establishment, headquarters, number of employees
- Core business description (2–3 sentences)
- Key business segments
- Geographic presence

## 3. Key Financial Highlights
Extract all available financial data and present as a table:
| Metric | FY[year-2] | FY[year-1] | FY[year] | Projected |
- Revenue, EBITDA, Net Profit, Gross Margin %, EBITDA Margin %
- {calc_rules}

## 4. Investment Highlights (5–7 bullet points)
Strong, specific reasons why this is a compelling investment opportunity.

## 5. Use of Proceeds
How will the capital be deployed? Be specific.

## 6. Key Value Drivers
What makes this company uniquely valuable?

## 7. Transaction Rationale
Why now? Strategic fit, market timing, growth inflection.

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"investment_thesis": """
Write a detailed INVESTMENT THESIS section for the CIM.

Cover ALL of the following with depth and specificity:

## 1. Why Invest Now — Macro & Micro Tailwinds
- Market timing and why this is the optimal entry point
- Macro trends benefiting the company
- Regulatory or policy tailwinds

## 2. Platform for Market Entry & Growth
- Geographic expansion opportunities
- New customer segment access
- Distribution channel leverage

## 3. Competitive Moats & Differentiation
- Unique IP, technology, or proprietary processes
- Switching costs for customers
- Brand strength and relationships
- Barriers to entry

## 4. Revenue Growth Levers
- Organic growth: volume, pricing, new products
- Inorganic: M&A pipeline, strategic alliances
- Cross-sell / upsell opportunities

## 5. Operational Excellence & Margin Expansion
- Cost optimization opportunities
- Process automation potential
- Scalability of the business model
{calc_rules}

## 6. Management Team Strength
- Experience, track record, and depth of the management team

## 7. Exit Opportunities
- Potential strategic buyers, financial sponsors
- IPO readiness
- Historical M&A comparable transactions with multiples

## 8. Financial Return Potential
- IRR scenarios (base, bull, bear)
- Exit multiple assumptions (EV/EBITDA, P/E)

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"market_overview": """
Write a comprehensive MARKET OVERVIEW section for the CIM.

## 1. Industry Definition & Scope
- Precise definition of the industry/sector
- Key sub-segments and their relative sizes
- Value chain description

## 2. Market Size & Growth
- Total Addressable Market (TAM) — global and domestic
- Serviceable Addressable Market (SAM)
- Serviceable Obtainable Market (SOM)
- Historical market size (3–5 years) and CAGR
- Projected market size (5 years forward)
{calc_rules}

## 3. Key Market Trends
- 5–7 major trends with data backing
- Technology disruption drivers
- Consumer/customer behavior shifts
- Regulatory changes

## 4. Competitive Landscape
Create a detailed competitor analysis:
| Competitor | Revenue | Market Share | Key Strengths | Weaknesses |
- Top 5–8 competitors
- Market positioning map description

## 5. Company's Competitive Position
- Market share (current and trended)
- Competitive advantages
- Porter's Five Forces brief analysis

## 6. Regulatory Environment
- Key regulations, licensing requirements
- Recent regulatory changes and impact
- Compliance landscape

## 7. Demand Drivers & Growth Catalysts
- What is driving demand growth?
- Key customers or sectors driving volume

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"company_overview": """
Write a detailed COMPANY OVERVIEW section for the CIM.

## 1. Company History & Milestones
- Year of incorporation, key milestones as a timeline
- Evolution of the business model
- Major achievements

## 2. Business Description
- What the company does in 2–3 paragraphs
- Core value proposition
- How the company makes money

## 3. Business Segments
For each segment:
- Description, revenue contribution (% and absolute), growth rate
- Key customers, key products/services

## 4. Geographic Presence
- HQ location
- Branch offices, plants, warehouses
- Revenue by geography table

## 5. Corporate Structure
- Legal entity type
- Shareholding pattern / ownership structure
- Subsidiaries and their roles

## 6. Key Financial Summary
| Metric | FY[Y-3] | FY[Y-2] | FY[Y-1] | FY[Y] |
Include: Revenue, EBITDA, EBITDA%, Net Profit, Net Worth, Debt, Cash
{calc_rules}

## 7. Recent Developments & News
- Last 12–18 months key events
- New product launches, partnerships, expansions

## 8. ESG & Sustainability
- Key ESG initiatives and metrics
- Certifications, awards

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"products_services": """
Write a detailed PRODUCTS & SERVICES section for the CIM.

## 1. Product/Service Portfolio Overview
- Complete list of all products and services
- Categorization into product lines / segments
- Revenue contribution of each line (table)

## 2. Detailed Product/Service Descriptions
For each major product/service:
- Description and functionality
- Target customer segment
- Differentiating features vs. competition
- Pricing model (unit price, subscription, project-based, etc.)
- Gross margin contribution
- Stage of maturity (early, growth, mature)

## 3. Technology & Innovation
- Proprietary technology, patents, trade secrets
- R&D investments (as % of revenue, absolute)
- Innovation pipeline and roadmap

## 4. Product Pipeline
- Products/services in development
- Expected launch timelines
- Market opportunity for each

## 5. Regulatory Approvals & Certifications
- All relevant certifications, licenses for products
- Status of pending approvals

## 6. Customer Value Proposition
- ROI/value delivered to customers
- Case studies / customer success metrics (anonymized if needed)

## 7. Revenue Model & Pricing
- Revenue streams breakdown
- Pricing tiers and strategy
- Recurring vs. one-time revenue split

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"revenue_profile": """
Write a detailed REVENUE PROFILE section for the CIM.

{calc_rules}

## 1. Revenue Summary
- Total revenue for last 3–5 years as a table
- Calculate and show: YoY growth %, CAGR
- Compare to industry growth rate

## 2. Revenue by Segment/Product Line
| Segment | FY[Y-2] | FY[Y-1] | FY[Y] | % of Total | Growth % |
- Detailed breakdown with commentary on each segment

## 3. Revenue by Geography
| Region | Revenue | % of Total | YoY Growth |
- Commentary on geographic strategy

## 4. Revenue by Customer Type
- Enterprise vs. SME vs. Retail split
- Top 10 customer concentration analysis
- Largest single customer as % of revenue
- Customer lifetime value (CLV) estimates

## 5. Revenue Stability & Predictability
- Recurring revenue %
- Contract durations and renewal rates
- Pipeline and backlog analysis (with values)
- Revenue visibility (% of next year revenue that is contracted)

## 6. Unit Economics
- Customer Acquisition Cost (CAC)
- LTV:CAC ratio
- Payback period
- Net Revenue Retention (NRR) / Dollar retention
- Average Revenue Per User (ARPU)

## 7. Revenue Projections (3–5 years)
Build year-by-year projection table:
| Year | Revenue | Growth % | EBITDA | EBITDA% |
- State assumptions clearly
- Show calculations step by step

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"employee_profile": """
Write a detailed EMPLOYEE PROFILE section for the CIM.

## 1. Workforce Overview
- Total headcount (current and historical trend)
- Full-time vs. part-time vs. contract split
- YoY headcount growth

## 2. Employee Distribution
| Function | Headcount | % of Total |
- Sales & Marketing, Engineering/Tech, Operations, Finance, Admin, R&D, etc.

## 3. Geographic Distribution
- Employees by location/office

## 4. Talent Quality & Expertise
- Average years of experience
- Percentage with advanced degrees / certifications
- Key specialized skills and expertise
- Depth of management bench

## 5. Compensation & Benefits
- Average compensation (ranges by level if available)
- Benefits structure (health, equity, bonuses)
- Equity/ESOP program details

## 6. Culture & Engagement
- Culture values and EVP (Employee Value Proposition)
- Employee satisfaction / eNPS scores
- Glassdoor / employer brand metrics

## 7. Attrition & Retention
- Annual attrition rate (vs. industry benchmark)
- Tenure distribution
- Key retention strategies

## 8. HR Policies & Training
- Training investment per employee
- L&D programs
- Succession planning

## 9. Labor Relations
- Union membership (if any)
- Key labor agreements
- Workplace safety metrics

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"customer_profile": """
Write a detailed CUSTOMER PROFILE section for the CIM.

## 1. Customer Base Overview
- Total number of active customers (current and historical)
- Customer growth rate (YoY, CAGR)
- Customer composition (enterprise, mid-market, SME, retail)

## 2. Customer Segmentation
| Segment | # Customers | Revenue | % of Total | Avg. Contract Value |
- Detailed analysis of each segment
- Penetration rates and market share within each segment

## 3. Top Customer Analysis
- Revenue concentration: top 1, 5, 10, 20 customers as % of total revenue
- Longevity of key relationships (years)
- Contract terms and renewal status
- Any customer concentration risks and mitigants

## 4. Customer Acquisition
- Primary acquisition channels
- CAC by channel
- Sales cycle length
- Win rate

## 5. Customer Retention & Loyalty
- Churn rate (gross and net)
- Net Promoter Score (NPS) or CSAT
- Customer testimonials / case studies
- Renewal rates

## 6. Customer Pain Points & Value Delivered
- Problems the company solves
- Measurable ROI delivered to customers
- Switching costs

## 7. Geographic Customer Distribution
- Revenue by customer geography
- Largest markets and penetration rates

## 8. Growth Opportunities Within Customer Base
- Cross-sell / upsell potential
- Wallet share analysis
- Pipeline from existing customers

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"financials": """
Write a comprehensive FINANCIALS section for the CIM.

{calc_rules}

## 1. Income Statement Summary (Historical)
Create detailed tables for 3–5 years:

| Line Item | FY[Y-4] | FY[Y-3] | FY[Y-2] | FY[Y-1] | FY[Y] |
- Revenue (by segment if available)
- Cost of Goods Sold / Direct Costs
- GROSS PROFIT
- Gross Margin %
- Operating Expenses (breakdown: S&M, R&D, G&A)
- EBITDA
- EBITDA Margin %
- D&A
- EBIT
- Interest Expense
- PBT (Profit Before Tax)
- Tax
- PAT (Profit After Tax)
- Net Margin %

Show YoY growth % for each key line. Calculate CAGR for Revenue and EBITDA.

## 2. Balance Sheet Summary
| Line Item | FY[Y-2] | FY[Y-1] | FY[Y] |
- Total Assets, Total Liabilities, Total Equity
- Cash & equivalents, Receivables, Inventory
- PP&E, Intangibles, Goodwill
- Short-term debt, Long-term debt
- Net Debt = Total Debt - Cash

## 3. Cash Flow Summary
| Line Item | FY[Y-2] | FY[Y-1] | FY[Y] |
- Operating Cash Flow (OCF)
- Capital Expenditures (Capex)
- Free Cash Flow (FCF) = OCF - Capex
- FCF Margin % = FCF / Revenue × 100

## 4. Key Financial Ratios
| Ratio | FY[Y-2] | FY[Y-1] | FY[Y] | Industry Avg |
- Profitability: Gross Margin, EBITDA Margin, Net Margin, ROE, ROA, ROCE
- Liquidity: Current Ratio, Quick Ratio
- Leverage: Debt/Equity, Net Debt/EBITDA, Interest Coverage
- Efficiency: Asset Turnover, Receivables Days, Payables Days, Inventory Days

## 5. Working Capital Analysis
- Working Capital = Current Assets - Current Liabilities
- Cash Conversion Cycle analysis

## 6. Financial Projections (5 Years)
Build a detailed financial model:
| Item | FY[Y+1]E | FY[Y+2]E | FY[Y+3]E | FY[Y+4]E | FY[Y+5]E |
- Revenue (with growth % assumption stated)
- EBITDA (with margin assumption stated)
- Net Profit
- Capex
- FCF

State ALL assumptions:
- Revenue growth rate basis (market share gain, pricing, volume)
- Margin improvement pathway
- Capex intensity
- Working capital normalization

## 7. Valuation Benchmarks
| Method | Value (Low) | Value (Mid) | Value (High) |
- EV/EBITDA (comparables range + implied value)
- P/E (comparables range + implied value)
- DCF (WACC assumption, terminal growth rate)
- EV/Revenue (for high-growth companies)

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",

"management_structure": """
Write a detailed MANAGEMENT STRUCTURE section for the CIM.

## 1. Organizational Overview
- Total management team size
- Organizational structure description (flat, divisional, matrix, etc.)
- Reporting lines

## 2. Board of Directors
For each board member:
| Name | Designation | Background | Years on Board | Key Expertise |
- Professional biography (2–3 sentences each)
- Board committees (Audit, Risk, Remuneration, etc.)
- Independent vs. executive directors

## 3. Senior Leadership Team
For each C-suite / VP-level executive:
- Name, Title, Years with Company, Prior Experience
- Key achievements and contributions
- Education and certifications

Format as structured bios:
**[Name]** — [Title]
[2–3 sentence professional bio with specific achievements and tenure]

## 4. Key Management Depth
- Depth of the management bench below C-suite
- Critical knowledge holders and succession plans
- Retention agreements / equity incentives for key personnel

## 5. Corporate Governance
- Board composition and independence
- Key governance policies
- Audit committee, risk management framework
- Related party transactions disclosure

## 6. Organizational Chart (Textual Description)
Describe the org chart structure with reporting lines.

## 7. Management Track Record
- Previous companies built / exited
- Specific metrics achieved under current leadership:
  - Revenue growth during tenure
  - Products launched
  - Markets entered
  - Team built

## 8. Post-Transaction Role
- Management's intended role post-acquisition/investment
- Retention plan for key executives
- Any planned management additions

CONTEXT FROM UPLOADED DOCUMENTS:
{context}
{chart_instruction}
""",
}


# ─────────────────────────────────────────────
# CIM Generator Class
# ─────────────────────────────────────────────

SECTION_QUERIES = {
    "executive_summary": ["company overview", "revenue EBITDA profit", "investment opportunity funding", "business model", "key highlights"],
    "investment_thesis": ["investment rationale", "competitive advantage", "growth strategy", "synergies", "exit strategy", "market opportunity"],
    "market_overview": ["market size TAM SAM SOM", "industry trends", "competitors", "market growth CAGR", "regulatory environment"],
    "company_overview": ["company history", "business segments", "corporate structure", "headquarters employees", "milestones"],
    "products_services": ["products services", "product pipeline", "pricing model", "technology patents", "product revenue"],
    "revenue_profile": ["revenue streams", "revenue by segment", "unit economics CAC LTV", "recurring revenue", "revenue projections"],
    "employee_profile": ["employees headcount", "workforce management", "attrition salary", "HR policies", "org structure"],
    "customer_profile": ["customers clients", "top customers revenue concentration", "customer acquisition", "NPS churn retention"],
    "financials": ["revenue EBITDA profit", "balance sheet assets liabilities", "cash flow", "financial projections", "valuation ratios"],
    "management_structure": ["management team CEO CFO", "board of directors", "governance", "organizational structure", "leadership experience"],
}


class CIMGenerator:
    def __init__(self, rag: RAGService, cfg: dict):
        self.rag = rag
        self.cfg = cfg
        self.gateway = LLMGateway.from_config(cfg)

    async def generate_section(self, section_name: str) -> dict:
        queries = SECTION_QUERIES.get(section_name, [section_name])
        context = await self.rag.get_all_context_async(queries, max_chars=12000)

        prompt_template = SECTION_PROMPTS.get(section_name, "")
        if not prompt_template:
            prompt_template = f"Write a detailed {section_name} section for a CIM.\n\nCONTEXT:\n{{context}}\n{{chart_instruction}}"

        prompt = prompt_template.format(
            context=context or "No documents uploaded yet. Write based on best practices for a CIM.",
            calc_rules=FINANCIAL_CALC_RULES,
            chart_instruction=CHART_INSTRUCTION,
        )

        response = await self.gateway.generate(
            LLMGenerateRequest(
                provider=self.cfg.get("llm_provider", "auto"),
                model=self.cfg.get("llm_model"),
                max_tokens=4096,
                temperature=0.2,
                messages=[
                    GatewayMessage(role="system", content=SYSTEM_PROMPT),
                    GatewayMessage(role="user", content=prompt),
                ],
            )
        )

        raw_content = str(response)
        content, charts = _extract_charts(raw_content)

        return {
            "section": section_name,
            "content": content,
            "charts": charts,
            "raw": raw_content,
        }

    async def chat(self, message: str) -> str:
        context = await self.rag.get_context_async(message, k=8)
        prompt = f"""You are an expert investment banker helping analyse a company for a CIM.
A user is asking questions about the uploaded company documents.
Answer accurately and specifically using only the context provided.
If the information is not in the context, say so clearly.

CONTEXT FROM DOCUMENTS:
{context}

USER QUESTION: {message}

Provide a detailed, accurate answer. Include specific numbers and metrics where available."""

        response = await self.gateway.generate(
            LLMGenerateRequest(
                provider=self.cfg.get("llm_provider", "auto"),
                model=self.cfg.get("llm_model"),
                max_tokens=2048,
                temperature=0.2,
                messages=[
                    GatewayMessage(
                        role="system",
                        content="You are an expert M&A advisor and financial analyst. "
                        "Answer questions about company documents accurately.",
                    ),
                    GatewayMessage(role="user", content=prompt),
                ],
            )
        )
        return str(response)


def _extract_charts(content: str):
    """Parse ```chart_data ... ``` blocks from LLM response."""
    chart_pattern = re.compile(r"```chart_data\s*([\s\S]*?)```", re.MULTILINE)
    charts = []
    cleaned = content

    for match in chart_pattern.finditer(content):
        raw_json = match.group(1).strip()
        try:
            data = json.loads(raw_json)
            if isinstance(data, list):
                charts.extend(data)
            elif isinstance(data, dict):
                charts.append(data)
        except json.JSONDecodeError:
            pass
        cleaned = cleaned.replace(match.group(0), "")

    return cleaned.strip(), charts
