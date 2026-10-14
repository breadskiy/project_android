with open('lib/main.dart', 'r', encoding='utf-8') as f:
    main_lines = f.readlines()

def print_range(lines, start, end, label):
    print(f"=== {label} (Lines {start}-{end}) ===")
    for i in range(start-1, min(end, len(lines))):
        print(f"{i+1}: {lines[i]}", end='')
    print()

# 1. LoginPage._login
print_range(main_lines, 175, 220, "LoginPage._login")
# 2. RegisterPage._register
print_range(main_lines, 515, 560, "RegisterPage._register")
# 3. ListDetailsPage._addItemWithText
print_range(main_lines, 3295, 3335, "ListDetailsPage._addItemWithText")
# 4. ListDetailsPage._toggleItem
print_range(main_lines, 3515, 3545, "ListDetailsPage._toggleItem")
