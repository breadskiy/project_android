main_file = r'd:\project_android\lib\main.dart'

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove _TransferDialogButton
p_btn_start = content.find('class _TransferDialogButton extends StatelessWidget {')
p_btn_end = content.find('class _ListDetailsPageState extends State<ListDetailsPage> {')
if p_btn_start != -1 and p_btn_end != -1:
    content = content[:p_btn_start] + content[p_btn_end:]
    print("1. Removed _TransferDialogButton")

# 2. Remove _baseProductsRu, _baseProductsEn, _aliases from _ListDetailsPageState
p_lists_start = content.find('  final List<String> _baseProductsRu = const [')
p_lists_end = content.find('  @override\n  void initState() {')
if p_lists_start != -1 and p_lists_end != -1:
    content = content[:p_lists_start] + content[p_lists_end:]
    print("2. Removed hardcoded product arrays from _ListDetailsPageState")

# 3. Remove _ProductSuggestion class
p_sugg_start = content.find('class _ProductSuggestion {')
p_sugg_end = content.find('class _ShoppingItem {')
if p_sugg_start != -1 and p_sugg_end != -1:
    content = content[:p_sugg_start] + content[p_sugg_end:]
    print("3. Removed _ProductSuggestion class")

# 4. Handle deprecated activeColor on Switch in _ProfileHomeView
switch_target = 'Switch(\n                          value: aiSuggestionsEnabled,\n                          activeColor: _authBlue,\n                          onChanged: onToggleAiSuggestions,\n                        )'
switch_replacement = '// ignore: deprecated_member_use\n                        Switch(\n                          value: aiSuggestionsEnabled,\n                          activeColor: _authBlue,\n                          onChanged: onToggleAiSuggestions,\n                        )'
if switch_target in content:
    content = content.replace(switch_target, switch_replacement)
    print("4. Added ignore on Switch activeColor")

with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Finished clean_final_warnings!")
