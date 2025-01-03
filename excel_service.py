import datetime
import uuid
import logging
from google.oauth2.service_account import Credentials
import gspread

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ExcelService:
    def __init__(self):
        # Initialize Google Sheets credentials
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        
        credentials = Credentials.from_service_account_file(
            'key_google_drive.json', 
            scopes=scope
        )
        
        gc = gspread.authorize(credentials)
        self.sheet = gc.open_by_key('16Y8kKLPpd-K1xNWHP9Hu3z07IVnZmXF4K4OSUbt87gA').sheet1
        
        # Store used IDs
        self.used_ids = set()
        self._load_existing_ids()
        
        # Check and create headers if needed
        self._ensure_headers()
        logger.info("Excel service initialized successfully")

    def _load_existing_ids(self):
        """Load existing IDs from sheet"""
        try:
            # Get all IDs from first column (excluding header)
            ids = self.sheet.col_values(1)[1:]
            self.used_ids.update(ids)
            logger.info(f"Loaded {len(self.used_ids)} existing IDs")
        except Exception as e:
            logger.error(f"Error loading existing IDs: {e}")

    def _ensure_headers(self):
        """Ensure sheet has proper headers"""
        headers = [
            "Investment ID",
            "Date",
            "Telegram ID",
            "Full Name",
            "Investment Amount $",
            "Email",
            "Transaction Hash",
            "Wallet Address"
        ]
        
        try:
            existing_headers = self.sheet.row_values(1)
            if not existing_headers:
                self.sheet.insert_row(headers, 1)
                logger.info("Created headers in sheet")
            else:
                logger.info("Headers already exist in sheet")
        except Exception as e:
            logger.error(f"Error checking/creating headers: {e}")

    def get_next_id(self):
        """Generate unique ID"""
        while True:
            # Generate ID using timestamp and random component
            timestamp = datetime.datetime.now().strftime('%H%M')
            random_part = str(uuid.uuid4())[:4].upper()
            new_id = f"{timestamp}{random_part}"
            
            # Check if ID is unique
            if new_id not in self.used_ids:
                self.used_ids.add(new_id)
                logger.info(f"Generated new unique ID: {new_id}")
                return new_id

    def _find_row_by_investment_id(self, investment_id):
        """Find row number by investment ID"""
        try:
            column_values = self.sheet.col_values(1)  # Get all values in first column
            for idx, value in enumerate(column_values, start=1):
                if value == investment_id:
                    return idx
            return None
        except Exception as e:
            logger.error(f"Error finding row: {e}")
            return None

    def save_user_data(self, investment_id, telegram_id, full_name, investment_amount, email, tx_hash="", wallet_address=""):
        """Save or update user data in Google Sheets"""
        try:
            row_data = [
                investment_id,
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                telegram_id,
                full_name,
                investment_amount,
                email,
                tx_hash,
                wallet_address
            ]
            
            # Check if row with this investment_id already exists
            existing_row = self._find_row_by_investment_id(investment_id)
            
            if existing_row and (tx_hash or wallet_address):
                # Update only transaction hash and wallet address in existing row
                if tx_hash:
                    self.sheet.update_cell(existing_row, 7, tx_hash)
                if wallet_address:
                    self.sheet.update_cell(existing_row, 8, wallet_address)
                logger.info(f"Updated existing row for investment ID: {investment_id}")
            else:
                # Add new row if it doesn't exist
                self.sheet.append_row(row_data)
                logger.info(f"Added new row for investment ID: {investment_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error saving to sheet: {e}")
            return False 