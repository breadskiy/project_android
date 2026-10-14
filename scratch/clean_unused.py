import re

main_file = r'd:\project_android\lib\main.dart'

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove _baseProductsEn and _aliases in _SearchTabState
# Find between final List<String> _baseProductsRu and class ListsPage
p1 = content.find('  final List<String> _baseProductsEn = const [')
p2 = content.find('  Future<String?> _createListDialog')
if p1 != -1 and p2 != -1 and p1 < p2:
    content = content[:p1] + content[p2:]
    print("Removed _baseProductsEn and _aliases from _SearchTabState")

# 2. Remove _TransferDialogButton
btn_str = '''class _TransferDialogButton extends StatelessWidget {
  final String label;
  final VoidCallback onPressed;

  const _TransferDialogButton({
    required this.label,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: _ink,
          side: const BorderSide(color: _authBlue, width: 2),
          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(10),
          ),
        ),
        child: Text(
          label,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
    );
  }
}'''
if btn_str in content:
    content = content.replace(btn_str, '')
    print("Removed _TransferDialogButton")

# 3. Remove _baseProductsRu, _baseProductsEn, _aliases from _ListDetailsPageState
p3 = content.find('  final List<String> _baseProductsRu = const [')
p4 = content.find('  @override\n  void initState() {')
# make sure p3 is in ListDetailsPageState
ld_pos = content.find('class _ListDetailsPageState extends State<ListDetailsPage> {')
if p3 != -1 and p4 != -1 and ld_pos < p3 < p4:
    content = content[:p3] + content[p4:]
    print("Removed hardcoded catalog lists from _ListDetailsPageState")

# 4. Remove addSuggestion local function in _showSearchAddSheet
add_sugg_pattern = re.search(r'        Future<void> addSuggestion\(_ProductSuggestion s\) async \{[\s\S]*?\n        \}', content)
if add_sugg_pattern:
    content = content.replace(add_sugg_pattern.group(0), '')
    print("Removed addSuggestion from _showSearchAddSheet")

# 5. Remove _ProductSuggestion.empty
empty_sugg = '''  const _ProductSuggestion.empty()
      : ru = 'Nothing found / Ничего не найдено',
        en = '',
        isPlaceholder = true;'''
if empty_sugg in content:
    content = content.replace(empty_sugg, '')
    print("Removed _ProductSuggestion.empty")

with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Finished cleaning unused elements!")
