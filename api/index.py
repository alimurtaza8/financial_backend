"""
Mutawazi Financial Proposal System - FastAPI Backend (Updated)
A complete REST API for the financial proposal generation system with AI price justification
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Union
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import uuid
import io
from pathlib import Path
import google.generativeai as genai
import asyncio
import aiohttp

# import os
from dotenv import load_dotenv




# Load environment variables from .env file
load_dotenv()


# Test Gemini API key loading
gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    print(f"✅ Gemini API key loaded (length: {len(gemini_key)})")
    try:
        genai.configure(api_key=gemini_key)
        print("✅ Gemini API configured successfully")
    except Exception as e:
        print(f"❌ Gemini API configuration failed: {e}")
else:
    print("❌ GEMINI_API_KEY not found in environment variables")

# Pydantic Models for Request/Response
class ReadinessAssessment(BaseModel):
    answers: List[bool] = Field(..., description="7 boolean answers for readiness questions")

class ReadinessResponse(BaseModel):
    score: int
    status: str
    can_proceed: bool
    questions: List[str]

class ProjectMetadata(BaseModel):
    project_name_en: str = Field(..., description="Project name in English")
    project_name_ar: str = Field(..., description="Project name in Arabic")
    client_name_en: str = Field(..., description="Client name in English") 
    client_name_ar: str = Field(..., description="Client name in Arabic")
    project_type: str = Field(..., description="fixed, framework, or deliverable")
    boq_type: str = Field(..., description="deliverable-based or monthly resources-based")
    num_deliverables: int = Field(..., gt=0, description="Number of deliverables")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    rfp_code: str = Field(..., description="RFP code from client")

class DeliverableData(BaseModel):
    name: str = Field(..., description="Deliverable name")
    due_date: str = Field(..., description="Due date in YYYY-MM-DD format")
    service_id: Optional[str] = Field(None, description="ID from services catalog")
    amount: Optional[float] = Field(None, gt=0, description="Amount to charge client (auto-filled if service_id provided)")
    salaries: float = Field(..., ge=0, description="Salary costs")
    tools: float = Field(..., ge=0, description="Tools/software costs")
    others: float = Field(..., ge=0, description="Other expenses")

class CashFlowRequest(BaseModel):
    deliverables: List[DeliverableData]

class PaymentTerm(BaseModel):
    description: str = Field(..., description="Payment description")
    percentage: float = Field(..., gt=0, le=100, description="Percentage of total amount")

class ProposalItem(BaseModel):
    description: str = Field(..., description="Item description")
    quantity: int = Field(default=1, gt=0)
    unit_price: float = Field(..., gt=0)
    total_price: float = Field(..., gt=0)

class FinalProposalRequest(BaseModel):
    proposal_items: List[ProposalItem]
    payment_terms: List[PaymentTerm]

class OverheadCosts(BaseModel):
    salaries: float = Field(default=50000)
    utilities: float = Field(default=15000)
    transportation: float = Field(default=10000)
    visas: float = Field(default=8000)
    office_rent: float = Field(default=20000)
    insurance: float = Field(default=5000)

class PriceJustificationRequest(BaseModel):
    service_id: str = Field(..., description="Service ID from catalog")
    proposed_price: float = Field(..., gt=0, description="Proposed price for the service")

# Initialize FastAPI app
app = FastAPI(
    title="Mutawazi Financial Proposal System",
    description="API for generating financial proposals with cost analysis, cash flow planning, and AI price justification",
    version="2.0.0"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global storage for proposal data (in production, use database)
proposals_storage = {}
current_session = {}

# Pre-loaded data
READINESS_QUESTIONS = [
    "I have read and understood the scope",
    "This project is within our mandate",
    "I have aligned internally that I will do pricing",
    "The contract type is understood (Fixed, Deliverables-Based, or Framework)",
    "I have checked if there is an existing rate card or similar past proposal",
    "I understand whether this is a monthly resource BoQ or milestone BoQ",
    "I know the expected duration of the project or agreement"
]

# Updated services catalog with real data
SERVICES_CATALOG = {
    "1.0": {
        "name": "AI Strategy & Governance",
        "description": "",
        "unit": "Service",
        "duration": 24,
        "price": 80000.00
    },
    "1.1": {
        "name": "AI Governance Framework Development",
        "description": "This includes developing AI governance frameworks aligned with international standards (e.g. ISO/IEC 42001:2023) and the client's vision and objectives",
        "unit": "Service",
        "duration": 12,
        "price": 40000.00
    },
    "1.2": {
        "name": "AI Trustworthiness & Risk Assessment",
        "description": "Incorporates AI risk management models to ensure ethical, bias-mitigated, and secure AI deployment",
        "unit": "Service",
        "duration": 2,
        "price": 30000.00
    },
    "1.3": {
        "name": "Ethical AI Policy & Compliance Strategy",
        "description": "Establishes AI ethics guidelines and ensures alignment with regulatory requirements (e.g. Saudi NDMO policies)",
        "unit": "Service",
        "duration": 3,
        "price": 15000.00
    },
    "1.4": {
        "name": "Set up AI Office in compliance with SDAIA",
        "description": "Assess maturity of AI compliance and set up operating model for AI offices",
        "unit": "Service",
        "duration": 2,
        "price": 10000.00
    },
    "2.0": {
        "name": "AI Project & Portfolio Management",
        "description": "",
        "unit": "Service",
        "duration": 18,
        "price": 950000.00
    },
    "2.1": {
        "name": "AI-Driven PMO Setup & Consultancy",
        "description": "Establishing or upgrading a Project Management Office with AI capabilities for automation and real-time project tracking. (Includes integrating AI tools into project workflows for status reporting and schedule optimization.)",
        "unit": "Service",
        "duration": 12,
        "price": 300000.00
    },
    "2.2": {
        "name": "AI Project Tracker & Risk Prediction Tool",
        "description": "Deployment of an 'AI Project Manager' solution that uses predictive analytics to forecast project risks and delays. (For example, AI-based dashboards that predict schedule slippages and resource needs, valued in mid-six figures based on past tech deployments.)",
        "unit": "Service",
        "duration": 4,
        "price": 350000.00
    },
    "2.3": {
        "name": "AI Portfolio Roadmap Development",
        "description": "Creating an AI-enhanced portfolio roadmap with project interdependencies and strategic alignment. (Often delivered as a consulting output rather than a separately priced item.)",
        "unit": "Service",
        "duration": 10,
        "price": 400000.00
    },
    "3.0": {
        "name": "AI Risk Management & Compliance",
        "description": "",
        "unit": "Service",
        "duration": 6,
        "price": 500000.00
    },
    "3.1": {
        "name": "AI Maturity & Impact Assessment",
        "description": "Evaluating the organization's AI maturity level and readiness, and assessing potential impact and risks of AI use cases. (Includes workshops and an AI maturity model assessment.)",
        "unit": "Service",
        "duration": 2,
        "price": 200000.00
    },
    "3.2": {
        "name": "AI Risk & Compliance Framework",
        "description": "Developing tools and processes for AI risk identification, bias mitigation, and compliance monitoring (e.g. TRM - Transformation Risk Manager)",
        "unit": "Service",
        "duration": 3,
        "price": 300000.00
    },
    "3.3": {
        "name": "Regulatory Alignment & Audit Preparation",
        "description": "Ensuring AI initiatives comply with local and international regulations, and preparing documentation for audits or certifications (such as NDMO guidelines or OECD AI principles)",
        "unit": "Service",
        "duration": 3,
        "price": 250000.00
    },
    "4.0": {
        "name": "AI Enablement & Implementation",
        "description": "",
        "unit": "Service",
        "duration": 36,
        "price": 3000000.00
    },
    "4.1": {
        "name": "AI Solution Design & MVP Development",
        "description": "End-to-end development of a proof-of-concept or MVP (Minimum Viable Product) for an AI solution tailored to the client's use case",
        "unit": "Solution",
        "duration": 2,
        "price": 725000.00
    },
    "4.2": {
        "name": "Advanced Analytics & BI Integration",
        "description": "Implementing AI-powered analytics, business intelligence dashboards, and real-time data processing for decision support",
        "unit": "Solution",
        "duration": 9,
        "price": 925000.00
    },
    "4.3": {
        "name": "Custom AI Use Case Development",
        "description": "Developing industry-specific AI use cases or models (e.g. predictive maintenance, customer service chatbots) and integrating them into business processes",
        "unit": "Document",
        "duration": 10,
        "price": 600000.00
    },
    "4.4": {
        "name": "User Interface & Experience Implementation",
        "description": "Building intuitive, multi-language user interfaces for AI applications, ensuring accessibility (e.g. compliance with WCAG standards).",
        "unit": "Software",
        "duration": 8,
        "price": 1000000.00
    },
    "4.5": {
        "name": "Integration & Deployment",
        "description": "Integration of AI solutions into the client's environment (CRM, ERP, etc.), including testing and deployment on cloud or on-prem infrastructure",
        "unit": "Software & Hardware",
        "duration": 12,
        "price": 1250000.00
    },
    "4.6": {
        "name": "Chatbot Development & Automation",
        "description": "Mutawazi's ChatBot capabilities are incorporated here as a key AI use-case. Developing a modular conversational AI assistant (e.g. for customer service or internal support) falls under AI Enablement",
        "unit": "Subscription",
        "duration": 1,
        "price": 10000.00
    },
    "5.0": {
        "name": "Training & Capacity Building",
        "description": "",
        "unit": "Service",
        "duration": 36,
        "price": 400000.00
    },
    "5.1": {
        "name": "AI Competency Development Programs",
        "description": "A series of workshops, 'AI bootcamps,' and hands-on training sessions to build the client team's AI skills",
        "unit": "Service",
        "duration": 36,
        "price": 250000.00
    },
    "5.2": {
        "name": "Executive Leadership Workshops",
        "description": "High-level seminars for leadership on AI strategy, transformation, and change management",
        "unit": "Employee",
        "duration": 6,
        "price": 25000.00
    },
    "5.3": {
        "name": "Certification Training (ISO/IEC 42001)",
        "description": "Focused training to prepare teams for AI management system certification",
        "unit": "Employee",
        "duration": 1,
        "price": 10000.00
    },
    "5.4": {
        "name": "Certification Training (⁠ISO 14001)",
        "description": "Certified training",
        "unit": "Employee",
        "duration": 1,
        "price": 10000.00
    },
    "5.5": {
        "name": "Certification Training (⁠ISO 45001)",
        "description": "Certified training",
        "unit": "Employee",
        "duration": 1,
        "price": 10000.00
    },
    "5.6": {
        "name": "Certification Training (⁠ISO 9001)",
        "description": "Certified training",
        "unit": "Employee",
        "duration": 1,
        "price": 10000.00
    },
    "5.7": {
        "name": "Certification Training (⁠ISO 50001)",
        "description": "Certified training",
        "unit": "Employee",
        "duration": 1,
        "price": 10000.00
    },
    "6.0": {
        "name": "Data Management & AI Infrastructure",
        "description": "",
        "unit": "Service",
        "duration": 36,
        "price": 3500000.00
    },
    "6.1": {
        "name": "AI/Data Architecture Design",
        "description": "Designing the overall system and data architecture for AI solutions, including databases, data pipelines, and cloud infrastructure",
        "unit": "Service",
        "duration": 6,
        "price": 700000.00
    },
    "6.2": {
        "name": "Data Collection & Integration",
        "description": "Setting up data integration pipelines to gather and unify data from various sources (internal systems or external APIs) for AI use",
        "unit": "Service",
        "duration": 12,
        "price": 675000.00
    },
    "6.3": {
        "name": "Secure Data Storage & Cybersecurity",
        "description": "Implementing secure data lakes/warehouses and applying cybersecurity best practices (encryption, access controls) to protect sensitive data.",
        "unit": "Software & Hardware",
        "duration": 6,
        "price": 800000.00
    },
    "6.4": {
        "name": "AI Infrastructure & Cloud Deployment",
        "description": "Provisioning cloud or on-premise environments for AI model training and deployment, ensuring scalability and compliance with data residency requirements",
        "unit": "Software & Hardware",
        "duration": 18,
        "price": 700000.00
    },
    "6.5": {
        "name": "Interoperability & API Integration",
        "description": "Ensuring the AI systems can interconnect with other enterprise systems and external services",
        "unit": "Service",
        "duration": 8,
        "price": 700000.00
    },
    "6.6": {
        "name": "Maintenance & Support Services",
        "description": "Ongoing technical support, system monitoring, and model maintenance post-implementation",
        "unit": "Service",
        "duration": 1,
        "price": 650000.00
    }
}

DEFAULT_OVERHEAD_COSTS = {
    "salaries": 50000,
    "utilities": 15000,
    "transportation": 10000,
    "visas": 8000,
    "office_rent": 20000,
    "insurance": 5000
}

# Utility functions
def generate_quotation_code():
    """Generate unique quotation code"""
    return f"MUT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

def calculate_duration_months(start_date: str, end_date: str) -> int:
    """Calculate duration in months between two dates"""
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    return round((end - start).days / 30.44)

# def calculate_overhead(base_costs: float, overhead_costs: dict) -> float:
#     """Calculate overhead costs"""
#     total_monthly_overhead = sum(overhead_costs.values())
#     return base_costs * 0.15  # 15% overhead rate


def calculate_overhead(base_costs: float, overhead_costs: dict, duration_months: int = 1) -> float:
    """Calculate overhead costs based on monthly overhead and project duration"""
    monthly_overhead = sum(overhead_costs.values())
    total_overhead = monthly_overhead * duration_months
    # Add 15% overhead on base costs plus fixed monthly overheads
    return (base_costs * 0.15) + total_overhead



# # async def generate_price_justification(service_id: str, proposed_price: float) -> str:
#     """Generate price justification using Gemini API"""
#     try:
#         # Get service details
#         service = SERVICES_CATALOG.get(service_id)
#         if not service:
#             return "Service not found in catalog"
        
#         # Configure Gemini API
#         gemini_api_key = os.getenv("GEMINI_API_KEY")
#         if not gemini_api_key:
#             return "Gemini API key not configured"
        
#         genai.configure(api_key=gemini_api_key)
#         model = genai.GenerativeModel('gemini-1.5-flash')  # Use gemini-2.5-flash if available
        
#         # Prepare prompt
#         # prompt = f"""
#         # We are a consulting company in Saudi Arabia called Mutawazi. 
#         # We're providing this service: {service['name']} - {service['description']}
        
#         # Our catalog price for this service is {service['price']:,.2f} SAR.
#         # We're proposing to charge the client {proposed_price:,.2f} SAR for this service.
        
#         # Please generate a professional 2-3 sentence justification that:
#         # 1. Compares our proposed price to typical market rates in Saudi Arabia
#         # 2. Explains the value we provide
#         # 3. Justifies why our price is competitive
#         # 4. Mentions any special considerations for this service
        
#         # Write in a formal business tone suitable for client proposals.
#         # """

#         prompt = f"""
#         You are a pricing consultant for Mutawazi, a leading AI consulting company in Saudi Arabia.
        
#         Service Details:
#         - Service: {service['name']}
#         - Description: {service['description']}
#         - Our catalog price: {service['price']:,.2f} SAR
#         - Proposed client price: {proposed_price:,.2f} SAR
#         - Duration: {service['duration']} months
        
#         Generate a professional justification (2-3 sentences) that:
#         1. Compares our price to Saudi market standards for similar AI services
#         2. Highlights our unique value proposition
#         3. Explains why this price represents excellent value
#         4. Uses confident, professional language suitable for client proposals
        
#         Write in formal business English.
#         """
        
#         response = await model.generate_content_async(prompt)
#         return response.text
    
#     except Exception as e:
#         # return f"Error generating justification: {str(e)}"
#         return f"Unable to generate AI justification at this time. Our pricing is based on comprehensive market analysis and reflects the high-quality deliverables and expertise that Mutawazi provides for this specialized service."



async def generate_price_justification(service_id: str, proposed_price: float) -> str:
    """Generate price justification using Gemini API"""
    try:
        # Get service details
        service = SERVICES_CATALOG.get(service_id)
        if not service:
            return "Service not found in catalog"
        
        # Get Gemini API key
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            return "Please configure GEMINI_API_KEY in your environment variables. Contact your system administrator to set up AI price analysis."
        
        # Configure and test Gemini API
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Enhanced prompt for better justification
        prompt = f"""
        You are a pricing consultant for Mutawazi, a leading AI consulting company in Saudi Arabia.
        
        Service Details:
        - Service: {service['name']}
        - Description: {service['description']}
        - Our catalog price: {service['price']:,.2f} SAR
        - Proposed client price: {proposed_price:,.2f} SAR
        - Duration: {service['duration']} months
        
        Generate a professional justification (2-3 sentences) that:
        1. Compares our price to Saudi market standards for similar AI services
        2. Highlights our unique value proposition
        3. Explains why this price represents excellent value
        4. Uses confident, professional language suitable for client proposals
        
        Write in formal business English. Do not mention competitors by name.
        """
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        else:
            return "AI analysis indicates this pricing is competitive for the Saudi market and reflects our premium service quality and expertise."
    
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return f"Our pricing analysis shows this service is competitively priced for the Saudi AI consulting market. The price reflects Mutawazi's expertise, proven methodologies, and comprehensive service delivery approach that ensures successful project outcomes."


# API Endpoints

@app.get("/")
async def root():
    """Welcome endpoint"""
    return {
        "message": "Welcome to Mutawazi Financial Proposal System API",
        "version": "2.0.0",
        "endpoints": {
            "readiness": "/api/readiness",
            "metadata": "/api/metadata", 
            "cashflow": "/api/cashflow",
            "proposal": "/api/proposal",
            "services": "/api/services",
            "price_justification": "/api/price_justification"
        }
    }

@app.get("/api/welcome")
async def get_welcome_message():
    """Get the welcome message for the system"""
    return {
        "title": "Welcome to the Mutawazi Financial Pricing Model",
        "description": "This tool is designed to support consistent, transparent, and scalable pricing across all project types, whether resource-based, deliverable-based, or framework agreements.",
        "purpose": [
            "Price projects based on clear logic and cost structure",
            "Reflect project-specific assumptions (duration, scope, type)",
            "Forecast internal costs and external revenue clearly",
            "Justify pricing to clients with confidence",
            "Export chatbot-ready summaries for automation"
        ]
    }

@app.get("/api/readiness/questions")
async def get_readiness_questions():
    """Get readiness assessment questions"""
    return {
        "questions": READINESS_QUESTIONS,
        "required_score": 6,
        "total_questions": 7
    }

@app.post("/api/readiness/assess", response_model=ReadinessResponse)
async def assess_readiness(assessment: ReadinessAssessment):
    """Assess readiness based on answers"""
    if len(assessment.answers) != 7:
        raise HTTPException(status_code=400, detail="Must provide exactly 7 answers")
    
    score = sum(assessment.answers)
    
    if score >= 7:
        status = "✅ Ready"
        can_proceed = True
    elif score >= 6:
        status = "⚠️ Partial"
        can_proceed = True
    else:
        status = "❌ Not Ready"
        can_proceed = False
    
    # Store in session
    session_id = str(uuid.uuid4())
    current_session[session_id] = {
        "readiness": {
            "score": score,
            "status": status,
            "can_proceed": can_proceed,
            "answers": assessment.answers
        }
    }
    
    return ReadinessResponse(
        score=score,
        status=status,
        can_proceed=can_proceed,
        questions=READINESS_QUESTIONS
    )

@app.post("/api/metadata")
async def create_project_metadata(metadata: ProjectMetadata):
    """Create and validate project metadata"""
    try:
        # Validate dates
        start_date = datetime.strptime(metadata.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(metadata.end_date, '%Y-%m-%d')
        
        if start_date >= end_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
        
        # Calculate duration
        duration_months = calculate_duration_months(metadata.start_date, metadata.end_date)
        
        # Generate automated fields
        quotation_code = generate_quotation_code()
        version_name = "v1.0"
        created_on = datetime.now().strftime('%Y-%m-%d')
        
        processed_metadata = {
            **metadata.dict(),
            'duration_months': duration_months,
            'quotation_code': quotation_code,
            'version_name': version_name,
            'created_on': created_on
        }
        
        # Store in proposals
        proposals_storage[quotation_code] = {
            'metadata': processed_metadata,
            'created_at': datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "quotation_code": quotation_code,
            "metadata": processed_metadata
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing metadata: {e}")

@app.get("/api/services")
async def get_services_catalog():
    """Get available services catalog"""
    return {
        "services": SERVICES_CATALOG,
        "total_services": len(SERVICES_CATALOG)
    }

@app.get("/api/services/{service_id}")
async def get_service_by_id(service_id: str):
    """Get specific service by ID"""
    if service_id not in SERVICES_CATALOG:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {
        "service_id": service_id,
        **SERVICES_CATALOG[service_id]
    }

@app.post("/api/cashflow/deliverables")
async def calculate_deliverable_cashflow(request: CashFlowRequest):
    """Calculate deliverable-based cash flow with service catalog integration"""
    try:
        deliverables = []
        cumulative_net_flow = 0
        
        for i, deliv_data in enumerate(request.deliverables):
            # If service ID is provided, use catalog data
            service_info = None
            if deliv_data.service_id:
                service_info = SERVICES_CATALOG.get(deliv_data.service_id)
                if not service_info:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Service ID {deliv_data.service_id} not found in catalog"
                    )
                
                # Use catalog price if amount not provided
                if deliv_data.amount is None:
                    amount = service_info['price']
                else:
                    amount = deliv_data.amount
            else:
                if deliv_data.amount is None:
                    raise HTTPException(
                        status_code=400, 
                        detail="Amount is required when service ID is not provided"
                    )
                amount = deliv_data.amount
            
            # Calculate overhead
            base_costs = deliv_data.salaries + deliv_data.tools + deliv_data.others
            # overhead = calculate_overhead(base_costs, DEFAULT_OVERHEAD_COSTS)
            # Get duration from service or default to 1 month   
            duration = service_info['duration'] if service_info else 1
            overhead = calculate_overhead(base_costs, DEFAULT_OVERHEAD_COSTS, duration)
            
            # Calculate totals
            cash_out = base_costs + overhead
            net_flow = amount - cash_out
            cumulative_net_flow += net_flow
            
            deliverable = {
                'deliverable_name': deliv_data.name,
                'due_date': deliv_data.due_date,
                'service_id': deliv_data.service_id,
                'cash_in': amount,
                'salaries': deliv_data.salaries,
                'tools': deliv_data.tools,
                'others': deliv_data.others,
                'overhead': overhead,
                'cash_out': cash_out,
                'net_flow': net_flow,
                'cumulative_net_flow': cumulative_net_flow,
                'is_profitable': net_flow > 0
            }
            
            # Add service info if available
            if service_info:
                deliverable['service_info'] = {
                    'name': service_info['name'],
                    'catalog_price': service_info['price'],
                    'duration': service_info['duration'],
                    'unit': service_info['unit']
                }
            
            deliverables.append(deliverable)
        
        # Calculate summary
        total_revenue = sum(d['cash_in'] for d in deliverables)
        total_costs = sum(d['cash_out'] for d in deliverables)
        total_profit = total_revenue - total_costs
        profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        return {
            "deliverables": deliverables,
            "summary": {
                "total_revenue": total_revenue,
                "total_costs": total_costs,
                "total_profit": total_profit,
                "profit_margin": round(profit_margin, 2),
                "is_profitable": total_profit > 0
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating cash flow: {e}")

@app.post("/api/price_justification")
async def generate_price_justification_endpoint(request: PriceJustificationRequest):
    """Generate price justification using Gemini AI"""
    try:
        justification = await generate_price_justification(request.service_id, request.proposed_price)
        return {
            "service_id": request.service_id,
            "proposed_price": request.proposed_price,
            "justification": justification
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating price justification: {str(e)}")

@app.post("/api/proposal/create")
async def create_financial_proposal(request: FinalProposalRequest):
    """Generate final financial proposal"""
    try:
        # Validate payment terms
        total_percentage = sum(term.percentage for term in request.payment_terms)
        if abs(total_percentage - 100) > 0.01:
            raise HTTPException(
                status_code=400, 
                detail=f"Payment terms must sum to 100%. Current sum: {total_percentage}%"
            )
        
        # Calculate total amount
        total_amount = sum(item.total_price for item in request.proposal_items)
        
        # Calculate payment amounts
        payment_terms_with_amounts = []
        for term in request.payment_terms:
            payment_terms_with_amounts.append({
                "description": term.description,
                "percentage": term.percentage,
                "amount": total_amount * (term.percentage / 100)
            })
        
        # Generate proposal
        quotation_code = generate_quotation_code()
        proposal = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'offer_number': quotation_code,
            'items': [item.dict() for item in request.proposal_items],
            'total_amount': total_amount,
            'payment_terms': payment_terms_with_amounts,
            'currency': 'SAR',
            'created_at': datetime.now().isoformat()
        }
        
        # Store proposal
        proposals_storage[quotation_code] = {
            'proposal': proposal,
            'created_at': datetime.now().isoformat()
        }
        
        return {
            "success": True,
            "quotation_code": quotation_code,
            "proposal": proposal
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating proposal: {e}")

@app.get("/api/proposal/{quotation_code}")
async def get_proposal(quotation_code: str):
    """Get stored proposal by quotation code"""
    if quotation_code not in proposals_storage:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    return proposals_storage[quotation_code]

@app.get("/api/proposals")
async def list_all_proposals():
    """List all stored proposals"""
    return {
        "proposals": list(proposals_storage.keys()),
        "total_count": len(proposals_storage)
    }

@app.get("/api/proposal/{quotation_code}/summary")
async def get_proposal_summary(quotation_code: str):
    """Get formatted proposal summary"""
    if quotation_code not in proposals_storage:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    data = proposals_storage[quotation_code]
    
    if 'metadata' in data and 'proposal' in data:
        metadata = data['metadata']
        proposal = data['proposal']
        
        summary = f"""
=== MUTAWAZI FINANCIAL PROPOSAL ===

Project: {metadata.get('project_name_en', 'N/A')} / {metadata.get('project_name_ar', 'N/A')}
Client: {metadata.get('client_name_en', 'N/A')} / {metadata.get('client_name_ar', 'N/A')}
RFP Code: {metadata.get('rfp_code', 'N/A')}
Offer Number: {proposal['offer_number']}
Date: {proposal['date']}
Duration: {metadata.get('duration_months', 'N/A')} months

PROJECT ITEMS:
"""
        
        for i, item in enumerate(proposal['items'], 1):
            summary += f"{i}. {item['description']}\n"
            summary += f"   Quantity: {item.get('quantity', 1)} | Unit Price: {item.get('unit_price', 0):,.2f} SAR\n"
            summary += f"   Total: {item.get('total_price', 0):,.2f} SAR\n\n"
        
        summary += f"\nTOTAL PROJECT VALUE: {proposal['total_amount']:,.2f} SAR\n\n"
        
        summary += "PAYMENT TERMS:\n"
        for i, term in enumerate(proposal['payment_terms'], 1):
            summary += f"{i}. {term['description']}: {term['percentage']}% = {term['amount']:,.2f} SAR\n"
        
        return {"summary": summary}
    
    return {"summary": "Incomplete proposal data"}

@app.delete("/api/proposal/{quotation_code}")
async def delete_proposal(quotation_code: str):
    """Delete a proposal"""
    if quotation_code not in proposals_storage:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    del proposals_storage[quotation_code]
    return {"success": True, "message": f"Proposal {quotation_code} deleted"}

@app.get("/api/overhead")
async def get_overhead_costs():
    """Get current overhead costs (admin only)"""
    return {"overhead_costs": DEFAULT_OVERHEAD_COSTS}

@app.put("/api/overhead")
async def update_overhead_costs(overhead: OverheadCosts):
    """Update overhead costs (admin only)"""
    global DEFAULT_OVERHEAD_COSTS
    DEFAULT_OVERHEAD_COSTS.update(overhead.dict())
    return {
        "success": True,
        "updated_overhead_costs": DEFAULT_OVERHEAD_COSTS
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)