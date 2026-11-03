"""Every tool the app offers. To add one, see docs/adding-a-tool.md."""

from offline_tools.registry import Category, Tool
from offline_tools.ui.tools.convert_images_page import ConvertImagesPage
from offline_tools.ui.tools.excel_csv_page import ExcelCsvPage
from offline_tools.ui.tools.hash_checker import HashCheckerPage
from offline_tools.ui.tools.images_to_pdf_page import ImagesToPdfPage
from offline_tools.ui.tools.qr_check_page import QrCheckPage
from offline_tools.ui.tools.qr_page import QrPage
from offline_tools.ui.tools.redact_page import RedactPage
from offline_tools.ui.tools.scan_page import ScanPage
from offline_tools.ui.tools.watermark_page import WatermarkPage

ALL_TOOLS: tuple[Tool, ...] = (
    Tool(
        id="redact",
        name="Redact Documents",
        summary="Black out NRIC numbers, addresses or salaries before you send a PDF or photo.",
        category=Category.PRIVACY,
        page_factory=RedactPage,
        keywords=("redact", "black out", "hide", "censor", "nric", "payslip", "mask", "privacy"),
    ),
    Tool(
        id="qr-check",
        name="Check a QR Code",
        summary="See where a QR code or link really goes and spot scam warning signs.",
        category=Category.PRIVACY,
        page_factory=QrCheckPage,
        keywords=("qr", "scan", "scam", "phishing", "link", "safe", "paynow", "sgqr", "webcam"),
    ),
    Tool(
        id="scan-document",
        name="Scan Document",
        summary="Turn a phone photo of a document into a straight, clean black-and-white scan.",
        category=Category.PDF,
        page_factory=ScanPage,
        keywords=("scan", "scanner", "camscanner", "photo", "document", "crop", "straighten"),
    ),
    Tool(
        id="images-to-pdf",
        name="Images → PDF",
        summary="Combine photos or scans into one PDF, in the order you choose.",
        category=Category.PDF,
        page_factory=ImagesToPdfPage,
        keywords=("jpg", "png", "scan", "photo", "combine", "merge", "nric", "image to pdf"),
    ),
    Tool(
        id="convert-images",
        name="Convert Images",
        summary="Change images between JPG, PNG and WEBP, and strip location data.",
        category=Category.IMAGES,
        page_factory=ConvertImagesPage,
        keywords=("jpg", "jpeg", "png", "webp", "format", "exif", "batch", "convert"),
    ),
    Tool(
        id="watermark",
        name="Watermark Photos",
        summary="Add text or a logo on top of photos: any position, size, angle and opacity.",
        category=Category.IMAGES,
        page_factory=WatermarkPage,
        keywords=("watermark", "logo", "text", "overlay", "copyright", "id copy", "stamp"),
    ),
    Tool(
        id="excel-csv",
        name="Excel ↔ CSV",
        summary="Turn Excel workbooks into CSV files, or CSV files into Excel.",
        category=Category.DATA,
        page_factory=ExcelCsvPage,
        keywords=("xlsx", "csv", "spreadsheet", "sheet", "convert", "excel to csv"),
    ),
    Tool(
        id="qr-code",
        name="QR Code Generator",
        summary="Make a QR code for a link, text, Wi-Fi login or contact card.",
        category=Category.EVERYDAY,
        page_factory=QrPage,
        keywords=("qr", "wifi", "wi-fi", "vcard", "contact", "link", "barcode"),
    ),
    Tool(
        id="file-hash",
        name="Check File Hash",
        summary="Get a file's SHA-256 fingerprint and confirm a download wasn't tampered with.",
        category=Category.EVERYDAY,
        page_factory=HashCheckerPage,
        keywords=("sha256", "sha-256", "checksum", "verify", "md5", "integrity", "download"),
    ),
)
