from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

#To add confidence scores witht he value
#String value
class ConfidentStr(BaseModel):
    value: str = Field(description="The text value extracted from the document")
    confidence: float = Field(
        ge=0.0, 
        le=1.0, 
        description="How certain you are of this exact value, 0.0-1.0. Score low if the text is blurry, cut off, or ambigious."
    )

#Float value
class ConfidentFloat(BaseModel):
    value: float = Field(description="The numeric value extracted from the document")
    confidence: float = Field(
        ge=0.0, 
        le=1.0, 
        description="How certain you are of this exact value, 0.0-1.0. Score low if the text is blurry, cut off, or ambigious."
    )


#Items in a line on the receipt
class LineItem(BaseModel):
    description: str = Field(description="Descriptionof the line item as printed")
    quantity: float = Field(description="Quantity purchased; 1 if not shown")
    unit_price: float = Field(description="The Price per unit; equal to amount if not shown")
    amount: float = Field(description="Total for this line")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in this entire line item, 0.0-1.0"
    )

class InvoiceSchema(BaseModel):
    vendor: ConfidentStr = Field(description="Vendor or merchant name")
    invoice_number: ConfidentStr = Field(
        description="Invoice or receipt number; empty string if absent"
    )
    date: ConfidentStr = Field(description="Document date in ISO format YYYY-MM-DD")
    currency: ConfidentStr = Field(description="ISO 4217 currency code, e.g. USD, INR")
    subtotal: ConfidentFloat = Field(description="Pre-tax subtotal; 0 if absent")
    tax: ConfidentFloat = Field(description="Total tax; 0 if absent")
    discount: ConfidentFloat = Field(
        description="Total of all deductions: discounts, coupons, credits; 0 if none"
    )
    additional_charges: ConfidentFloat = Field(
        description="Total of all extra charges beyond subtotal and tax: shipping, "
        "delivery, tips, service charges, deposits, fees; 0 if none"
    )
    total: ConfidentFloat = Field(description="Grand total")
    line_items: List[LineItem] = Field(description="All line items on the document")
    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence in the whole extraction"
    )

#Human Review
class FlaggedField(BaseModel):
    field_path: str = Field(description="Dotted path, e.g. 'total' or 'line_items[2]'")
    value: str
    confidence: float

#API Connections and Processing
#For All
class IngestResponse(BaseModel):
    doc_id: str     #ID for the doc
    filename: str       #Uploaded file
    status: str         #Status of process (approved, review, blocked)
    extraction: Optional[InvoiceSchema] = None      #Extracted data from file
    flagged_fields: List[FlaggedField] = []     #items under review
    blocked_reason: Optional[str] = None        #When blocked, indicates the reason
    cost_usd: float = 0.0       #the cost to process actually
    watermarked_image_url: Optional[str] = None     #store link for processed files

#For Human Review Items
class ReviewItem(BaseModel):
    doc_id: str     #doc id
    filename: str   #uploaded file
    created_at: datetime    #date of upload0
    extraction: InvoiceSchema   #full extraction of the Data
    flagged_fields: List[FlaggedField]      #Flagged rows
    watermarked_image_url: Optional[str] = None #Store link to the actual photo

#Correction for Flagged items
class FieldCorrection(BaseModel):
    field_path: str     #path to the flagged field
    corrected_value: str        #corrected value by human

#HUman approval after review
class ApproveRequest(BaseModel):
    doc_id: str     #do cid
    corrections: List[FieldCorrection] = []     #Corrected items

#Confirmation of approval
class ApproveResponse(BaseModel):
    doc_id: str     #id
    status: str     #now approved
    applied_corrections: int    #num of corrections

#Final summary after processing
class DocumentSummary(BaseModel):
    doc_id: str
    filename: str
    status: str
    vendor: Optional[str] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    created_at: datetime
    cost_usd: float = 0.0


class RejectRequest(BaseModel):
    doc_id: str
    reason: str = ""


class RejectResponse(BaseModel):
    doc_id: str
    status: str

