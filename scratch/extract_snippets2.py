with open('lib/main.dart', 'r', encoding='utf-8') as f:
    main_lines = f.readlines()

def print_range(lines, start, end, label):
    print(f"=== {label} (Lines {start}-{end}) ===")
    for i in range(start-1, min(end, len(lines))):
        print(f"{i+1}: {lines[i]}", end='')
    print()

# _ShoppingItem
print_range(main_lines, 5177, 5240, "_ShoppingItem")
# ListsPage._filtered
print_range(main_lines, 2360, 2390, "ListsPage._filtered")
