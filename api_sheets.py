import gspread
import random
from datetime import datetime

# chose in Step 1, call either service_account(), oauth() or api_key().
gc = gspread.service_account(filename="src-login.json")

# Open a sheet from a spreadsheet in one go
wks = gc.open("vpn-finance").sheet1

VPN_SALES_SHEET = "vpn-finance"

def add_vpn_sale(user_id, username, months, price):
    """Record VPN sale to Google Sheets with date, user info, duration, price and total profit"""
    try:
        import time

        # Open the VPN sales spreadsheet
        try:
            spreadsheet = gc.open(VPN_SALES_SHEET)
        except gspread.SpreadsheetNotFound:
            # Create spreadsheet if it doesn't exist
            spreadsheet = gc.create(VPN_SALES_SHEET)
            worksheet = spreadsheet.sheet1
            # Add headers
            headers = [["Дата", "ID пользователя", "Username", "Месяцев", "Цена (₽)"]]
            worksheet.update(headers, "A1:E1")
            worksheet.format("A1:E1", {"textFormat": {"bold": True}})
            print(f"Created new spreadsheet: {VPN_SALES_SHEET}")

        wks = spreadsheet.sheet1

        # Step 1: Find and clear old summary row by checking column D for SUM formula
        all_values = wks.get_all_values()
        summary_row_num = None
        for row_num in range(len(all_values), 1, -1):
            try:
                # Check the formula in column D of this row (where SUM formula is)
                cell = wks.acell(f"D{row_num}", value_render_option='FORMULA')
                cell_formula = cell.value if cell else ""
                if cell_formula and isinstance(cell_formula, str) and cell_formula.startswith("=SUM("):
                    wks.range(f"A{row_num}:E{row_num}").clear()
                    summary_row_num = row_num
                    print(f"Cleared old summary at row {row_num}")
                    time.sleep(0.5)
                    break
            except:
                continue
        
        # Step 2: Add new data row (use the cleared summary row position if available)
        if summary_row_num:
            insert_row = summary_row_num
        else:
            # Use get_all_values to get actual row count including empty rows
            all_values = wks.get_all_values()
            insert_row = len(all_values) + 1

        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        wks.update(
            [[current_date, str(user_id), username or "", months, price]],
            f"A{insert_row}:E{insert_row}",
            value_input_option="USER_ENTERED"
        )

        # Format data row with light gray background
        wks.format(f"A{insert_row}:E{insert_row}", {
            "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95}
        })

        print(f"Added VPN sale at row {insert_row}")

        # Step 3: Add new summary row below the data
        summary_row = insert_row + 1
        sum_end = summary_row - 1

        wks.update(
            [["", "", "ИТОГО:", f"=SUM(D2:D{sum_end})", f"=SUM(E2:E{sum_end})"]],
            f"A{summary_row}:E{summary_row}",
            value_input_option="USER_ENTERED"
        )

        # Format summary row with purple background (like add_order)
        wks.format(f"A{summary_row}:E{summary_row}", {
            "backgroundColor": {"red": 0.8, "green": 0.6, "blue": 1.0},
            "textFormat": {"bold": True}
        })

        print(f"Added summary at row {summary_row}")
        return True

    except Exception as e:
        print(f"Error in add_vpn_sale: {e}")
        return False

def validate_and_style_table(spreadsheet_name):
    """Validate table exists and apply dynamic styling. Returns True if successful."""
    try:
        # Try to open the spreadsheet
        spreadsheet = gc.open(spreadsheet_name)
        worksheet = spreadsheet.sheet1
        
        # Get the worksheet ID
        worksheet_id = worksheet.id
        
        # Apply conditional formatting (dynamic styling)
        body = {
            'requests': [
                {
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [
                                {
                                    'sheetId': worksheet_id,
                                    'startColumnIndex': 2,
                                    'endColumnIndex': 3
                                }
                            ],
                            'booleanRule': {
                                'condition': {
                                    'type': 'NUMBER_GREATER',
                                    'values': [{'userEnteredValue': '0'}]
                                },
                                'format': {
                                    'backgroundColor': { 
                                        'red': 0.8,
                                        'green': 1.0,
                                        'blue': 0.8
                                    }
                                }
                            }
                        },
                        'index': 0
                    }
                },
                {
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [
                                {
                                    'sheetId': worksheet_id,
                                    'startColumnIndex': 2,
                                    'endColumnIndex': 3
                                }
                            ],
                            'booleanRule': {
                                'condition': {
                                    'type': 'NUMBER_LESS',
                                    'values': [{'userEnteredValue': '0'}]
                                },
                                'format': {
                                    'backgroundColor': {
                                        'red': 1.0,
                                        'green': 0.8,
                                        'blue': 0.8
                                    }
                                }
                            }
                        },
                        'index': 1
                    }
                },
                {
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [
                                {
                                    'sheetId': worksheet_id,
                                    'startColumnIndex': 2,
                                    'endColumnIndex': 3
                                }
                            ],
                            'booleanRule': {
                                'condition': {
                                    'type': 'NUMBER_EQ',
                                    'values': [{'userEnteredValue': '0'}]
                                },
                                'format': {
                                    'backgroundColor': {
                                        'red': 0.9,
                                        'green': 0.9,
                                        'blue': 0.9
                                    }
                                }
                            }
                        },
                        'index': 2
                    }
                }
            ]
        }
        
        spreadsheet.batch_update(body)
        print(f"Conditional formatting applied successfully to {spreadsheet_name}")
        return True
        
    except gspread.SpreadsheetNotFound:
        print(f"Spreadsheet '{spreadsheet_name}' not found")
        return False
    except gspread.exceptions.APIError as e:
        print(f"API error accessing '{spreadsheet_name}': {e}")
        return False
    except Exception as e:
        print(f"Error validating/styling table '{spreadsheet_name}': {e}")
        return False

# Add row with automatic summary management
def clear_all_data():
    """Clear all data from worksheet and reset"""
    try:
        wks.clear()
        # Add headers
        wks.update([['Value A', 'Value B', 'Difference']], 'A1:C1')
        wks.format('A1:C1', {'textFormat': {'bold': True}})
        print("Cleared all data and reset headers")
    except Exception as e:
        print(f"Error clearing data: {e}")

def add_order(a_value, b_value, spreadsheet_name="ezh-fin-manager"):
    """Add row, clear old summary, and add new summary to specified spreadsheet"""
    try:
        import time
        
        # Open the specified spreadsheet
        spreadsheet = gc.open(spreadsheet_name)
        wks = spreadsheet.sheet1
        
        # Step 1: Find and clear old summary by checking cell formulas (not values)
        all_values = wks.get_all_values()
        summary_row_num = None
        for row_num in range(len(all_values), 1, -1):
            try:
                # Check the formula in column A of this row using FORMULA option
                cell = wks.acell(f"A{row_num}", value_render_option='FORMULA')
                cell_formula = cell.value if cell else ""
                if cell_formula and isinstance(cell_formula, str) and cell_formula.startswith("=SUM("):
                    wks.range(f"A{row_num}:C{row_num}").clear()
                    summary_row_num = row_num
                    print(f"Cleared old summary at row {row_num}")
                    time.sleep(0.5)  # Wait for clear to take effect
                    break
            except:
                continue
        
        # Step 2: Add new data row (use the cleared summary row position if available)
        if summary_row_num:
            insert_row = summary_row_num
        else:
            # Use get_all_values to get actual row count including empty rows
            all_values = wks.get_all_values()
            insert_row = len(all_values) + 1
        
        wks.update([[a_value, b_value, f"=A{insert_row}-B{insert_row}"]], 
                   f"A{insert_row}:C{insert_row}", 
                   value_input_option='USER_ENTERED')
        
        # Format cells A and B with light gray background
        wks.format(f"A{insert_row}:B{insert_row}", {
            'backgroundColor': {
                'red': 0.95,
                'green': 0.95,
                'blue': 0.95
            }
        })
        
        print(f"Added data row at {insert_row}")
        
        # Step 3: Add new summary row below the data
        summary_row = insert_row + 1
        sum_end = summary_row - 1
        
        wks.update([[f"=SUM(A2:A{sum_end})", 
                    f"=SUM(B2:B{sum_end})", 
                    f"=SUM(A2:A{sum_end})-SUM(B2:B{sum_end})"]], 
                   f"A{summary_row}:C{summary_row}", 
                   value_input_option='USER_ENTERED')
        
        wks.format(f"A{summary_row}:C{summary_row}", {
            'backgroundColor': {'red': 0.8, 'green': 0.6, 'blue': 1.0},
            'textFormat': {'bold': True}
        })
        
        print(f"Added new summary at row {summary_row} (sum up to row {sum_end})")
        return True
        
    except Exception as e:
        print(f"Error in add_order: {e}")
        return False

# Add summary row with totals and purple formatting
def add_summary_row():
    """Add summary row with totals and purple formatting"""
    try:
        # Find first empty row
        str_values = wks.col_values(1)  # Get all values from column A
        first_empty_row = len(str_values) + 1
        
        # Check if there's already a summary row (look for SUM formulas)
        summary_row_found = False
        for row_num in range(2, first_empty_row):
            try:
                cell_value = wks.acell(f"A{row_num}").value
                if cell_value and cell_value.startswith("=SUM("):
                    # Clear old summary row completely
                    wks.range(f"A{row_num}:C{row_num}").clear()
                    first_empty_row = row_num  # Use this row for new summary
                    summary_row_found = True
                    print(f"Cleared old summary row at {row_num}")
                    break
            except:
                continue
        
        # Add formulas for totals
        wks.update([[f"=SUM(A2:A{first_empty_row-1})", 
                    f"=SUM(B2:B{first_empty_row-1})", 
                    f"=SUM(A2:A{first_empty_row-1})-SUM(B2:B{first_empty_row-1})"]], 
                   f"A{first_empty_row}:C{first_empty_row}", 
                   value_input_option='USER_ENTERED')
        
        # Format summary row with purple background
        wks.format(f"A{first_empty_row}:C{first_empty_row}", {
            'backgroundColor': {
                'red': 0.8,
                'green': 0.6,
                'blue': 1.0
            },
            'textFormat': {
                'bold': True
            }
        })
        
        print(f"Summary row added at row {first_empty_row}")
        
    except Exception as e:
        print(f"Error adding summary row: {e}")

# Simple conditional formatting using direct API call
def apply_simple_formatting():
    """Apply basic formatting to column C"""
    try:
        # Try using the spreadsheet's batch_update method
        spreadsheet = gc.open("ezh-fin-manager")
        worksheet = spreadsheet.sheet1
        
        # Get the worksheet ID
        worksheet_id = worksheet.id
        
        # Use the spreadsheet's batch_update method
        body = {
            'requests': [
                {
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [
                                {
                                    'sheetId': worksheet_id,
                                    'startColumnIndex': 2,  # Column C (0-indexed)
                                    'endColumnIndex': 3
                                }
                            ],
                            'booleanRule': {
                                'condition': {
                                    'type': 'NUMBER_GREATER',
                                    'values': [{'userEnteredValue': '0'}]
                                },
                                'format': {
                                    'backgroundColor': { 
                                        'red': 0.8,
                                        'green': 1.0,
                                        'blue': 0.8
                                    }
                                }
                            }
                        },
                        'index': 0
                    }
                },
                {
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [
                                {
                                    'sheetId': worksheet_id,
                                    'startColumnIndex': 2,  # Column C (0-indexed)
                                    'endColumnIndex': 3
                                }
                            ],
                            'booleanRule': {
                                'condition': {
                                    'type': 'NUMBER_LESS',
                                    'values': [{'userEnteredValue': '0'}]
                                },
                                'format': {
                                    'backgroundColor': {
                                        'red': 1.0,
                                        'green': 0.8,
                                        'blue': 0.8
                                    }
                                }
                            }
                        },
                        'index': 1
                    }
                },
                {
                    'addConditionalFormatRule': {
                        'rule': {
                            'ranges': [
                                {
                                    'sheetId': worksheet_id,
                                    'startColumnIndex': 2,  # Column C (0-indexed)
                                    'endColumnIndex': 3
                                }
                            ],
                            'booleanRule': {
                                'condition': {
                                    'type': 'NUMBER_EQ',
                                    'values': [{'userEnteredValue': '0'}]
                                },
                                'format': {
                                    'backgroundColor': {
                                        'red': 0.9,
                                        'green': 0.9,
                                        'blue': 0.9
                                    }
                                }
                            }
                        },
                        'index': 2
                    }
                }
            ]
        }
        
        spreadsheet.batch_update(body)
        print("Conditional formatting applied successfully")
        
    except Exception as e:
        print(f"Error applying formatting: {e}")

