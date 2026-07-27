'''
schemas.py -> Defines the schema:
- COnfidence scores for Text/Numeric fields
- Line Items and Invoice Details (Date uses location to clear confusion of day <=12)
- Human Review through flagged fields
- Extraction schema - Auto approved, human review, approve, reject
- Document summary
'''

from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

#To add confidence scores witht he value and each field. [0.0, 1.0] and to extract information (Text/Numeric)
#String value
class ConfidentStr(BaseModel):
    value: str = Field(description="The text value extracted from the document")
    confidence: float = Field(ge=0.0, le=1.0, description="How certain you are of this exact value, 0.0-1.0. Score low if the text is blurry, cut off, poor quality, or ambigious.")

#Float value
class ConfidentFloat(BaseModel):
    value: float = Field(description="The numeric value extracted from the document")
    confidence: float = Field(ge=0.0, le=1.0, description="How certain you are of this exact value, 0.0-1.0. Score low if the text is blurry, cut off, poor quality, or ambigious.")



#Items in a line on the receipt, and invoice details
#LineItem for each product
class LineItem(BaseModel):
    description: str = Field(description="The description of the line item as printed")
    quantity: float = Field(description="The quantity purchased of the item. 1 if not shown")
    unit_price: float = Field(description="The price per unit of the item. Equal to item's final amount if not shown")
    amount: float = Field(description="The Total for this line item")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score in this entire line item, 0.0-1.0")

#Invoice details for full invoice, including vendor, date, currency, cost totals.
#two additional fields were included, discount (sales, cost reduced, coupons, etc) & additional charges (including shipping charges, tips, environmental charges, etc), that were not defined/included in above fields
#Each of these fields is either a ConfidentStr or ConfidentFloat based on the type. Thus, that is the object type instead of simple str/float.
class InvoiceSchema(BaseModel):
    vendor: ConfidentStr = Field(description="The vendor or merchant name on invoice")
    invoice_number: ConfidentStr = Field(description="The Invoice or receipt number. Empty string if absent or not there")
    date: ConfidentStr = Field(description="Document date in ISO format YYYY-MM-DD. Use the receipt's address, currency, and language to determine day/month order. If the order is still ambigious (both <= 12) and nothing resolves it, lower confidence to 0.6 or below.")        #ISO format. Checks location to choose and clarify for dates with month, date <=12 (like 6/11/2020) as different places read month/date in different manner.If still ambigious, lowers confidence.
    currency: ConfidentStr = Field(description="ISO 4217 currency code, example: USD, INR")
    subtotal: ConfidentFloat = Field(description="Pre-tax subtotal. 0 if absent")
    tax: ConfidentFloat = Field(description="Total tax. 0 if absent")
    discount: ConfidentFloat = Field(description="Total of all deductions: discounts, coupons, credits. 0 if none")
    additional_charges: ConfidentFloat = Field(description="Total of all extra charges beyond subtotal and tax: shipping, delivery, tips, service charges, deposits, fees. 0 if none")
    total: ConfidentFloat = Field(description="Grand total")
    line_items: List[LineItem] = Field(description="All the line items on the document")
    overall_confidence: float = Field(ge=0.0, le=1.0, description="The overall confidence score in the whole extraction")



#Human Review flagged field
class FlaggedField(BaseModel):
    field_path: str = Field(description="Dotted path, e.g. 'total' or 'line_items[2]'")
    value: str
    confidence: float
    reason: str = ""

#Extraction data and formats
#For All - General
class ExtractionResult(BaseModel):
    doc_id: str     #ID for the doc
    filename: str       #Uploaded file
    status: str         #Status of process (approved, review, blocked)
    extraction: Optional[InvoiceSchema] = None      #Extracted data from file. Optional as moderation may block extraction
    flagged_fields: List[FlaggedField] = []     #items under review
    blocked_reason: Optional[str] = None        #When blocked, indicates the reason
    cost_usd: float = 0.0       #the cost to process actually
    watermarked_image_url: Optional[str] = None     #store link for processed files. Optional as moderation may block extraction

#For Human Review Items
class ReviewItem(BaseModel):
    doc_id: str     #doc id
    filename: str   #uploaded file
    created_at: datetime    #date of upload
    extraction: InvoiceSchema   #full extraction of the Data
    flagged_fields: List[FlaggedField]      #Flagged rows
    watermarked_image_url: str   #Store link to the actual photo

#Correction for Flagged items
class FieldCorrection(BaseModel):
    field_path: str     #path to the flagged field
    corrected_value: str        #corrected value by human

#HUman approval after review
class ApproveRequest(BaseModel):
    doc_id: str     #doc id
    corrections: List[FieldCorrection] = []     #Corrected items

#Confirmation of approval
class ApproveResponse(BaseModel):
    doc_id: str     #id
    status: str     #now approved
    applied_corrections: int    #num of corrections

#HUman rejection after review
class RejectRequest(BaseModel):
    doc_id: str
    reason: str = ""    #reason of rejection

#Confirmation of rejection
class RejectResponse(BaseModel):
    doc_id: str
    status: str


#Final summary after processing
#some fields are Optional as moderation may block extraction
class DocumentSummary(BaseModel):
    doc_id: str
    filename: str
    status: str
    vendor: Optional[str] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    created_at: datetime
    cost_usd: float = 0.0
    blocked_reason: Optional[str] = None
    extraction: Optional[InvoiceSchema] = None