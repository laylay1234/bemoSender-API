"""
  GET CANADIAN PROVINCE CODE FROM POSTAL CODE
  REF_1: https://en.wikipedia.org/wiki/List_of_postal_codes_of_Canada:_B
  REF_2: http://www.columbia.edu/~fdc/postal/postal-ca.html

  Search for Canadian State code based on the first letter of the postal code
  RULES:
    - 1ST CHAR: NOT "D", "F", "I", "O", "Q", "U"
    - "XOA", "XOB", "XOC" is related to Nunavut (NU)
      while the rest of the "X" letter is related to North-West Territories (NT)
"""
#const {RegexPatterns} = require("./validation/schemas");
from loguru import logger
from postalcodes_ca import postal_codes

class StateCodeGenerator():
    def __init__(self) -> None:
        self.state_codes = {
            "CA": {
                "Alberta" : "AB",
                "British Columbia": "BC",
                "Manitoba": "MB",
                "New Brunswick": "NB",
                "Newfoundland and Labrador": "NL",
                "Nova Scotia":"NS",
                "Northwest Territory": "NT",
                "Ontario": "ON",
                "Prince Edward Island": "PE",
                "Quebec": "QC",
                "Saskatchewan": "SK",
                "Yukon": "YT",
                "Nunavut Territory": "NU",
            }
        }
        self.error_codes = {
            "invalid": "Invalid parameters",
            "missing": "Missing parameters",
            "nostate": "Unable to retrieve the[STATE_NAME] code.",
            "default": "Unknown error! Please try again later."
        }
    def get_state_code(self, postalCode, countryCode):
        try:
            if not isinstance(postalCode, str) or not isinstance(countryCode, str):
                return self.error_codes['missing']
            state_code = ""
            if countryCode.lower() == "ca":
                
                if " " in postalCode:
                    postalCode = postalCode.upper()
                    print(postalCode)
                    state_code = self.state_codes['CA'][postal_codes[postalCode].province]
                else:
                    postalCode = postalCode[:3] + " " + postalCode[3:]
                    postalCode = postalCode.upper()
                    state_code = self.state_codes['CA'][postal_codes[postalCode].province]
            elif countryCode.lower() == "us":
                pass
            if state_code == "":
                return self.error_codes['nostate']
            else:
                return state_code
        except Exception as e:
            logger.info(f"Verification{e}")
            return self.error_codes['default']
            
