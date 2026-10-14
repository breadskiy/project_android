main_file = r'd:\project_android\lib\main.dart'

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. In _SearchTabState: remove unused _noResultsSuggestion, _match, _addSuggestion
# Remove static const _noResultsSuggestion = _ProductSuggestion.empty();
content = content.replace('  static const _noResultsSuggestion = _ProductSuggestion.empty();\n', '')

# Remove _match method in _SearchTabState
match_code = '''  List<_ProductSuggestion> _match(String query) {
    final normalized = _normalizeQuery(query);
    if (normalized.isEmpty) return const [];

    final results = <_ProductSuggestion>[];
    for (var i = 0; i < _baseProductsRu.length; i++) {
      final ru = _baseProductsRu[i];
      final en = _baseProductsEn[i];
      final aliases = _aliases[i];

      final matches = <String>[ru, en, ...aliases]
          .map(_normalizeQuery)
          .any((value) => value.contains(normalized));

      if (matches) results.add(_ProductSuggestion(ru: ru, en: en));
    }
    return results;
  }'''

if match_code in content:
    content = content.replace(match_code, '')

add_suggestion_code = '''  Future<void> _addSuggestion(_ProductSuggestion suggestion) async {
    if (suggestion.isPlaceholder) return;
    await _addWithPicker(suggestion.ru);
    if (!mounted) return;
    _controller.clear();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Добавлено: ${suggestion.ru}'),
        duration: const Duration(milliseconds: 900),
      ),
    );
  }'''

if add_suggestion_code in content:
    content = content.replace(add_suggestion_code, '')

# 2. In ListsPage replenish onPressed: fix BuildContext async gap
old_btn = '''                                    onPressed: () async {
                                      Navigator.pop(context);
                                      if (_lists.isNotEmpty) {
                                        final target = _lists.first;
                                        await ApiService.instance.addItem(target.id, item.name);
                                        if (mounted) {
                                          ScaffoldMessenger.of(context).showSnackBar(
                                            SnackBar(content: Text('Товар "${item.name}" добавлен в список "${target.name}"')),
                                          );
                                          await refresh();
                                        }
                                      }
                                    },'''

new_btn = '''                                    onPressed: () async {
                                      final messenger = ScaffoldMessenger.of(context);
                                      Navigator.pop(context);
                                      if (_lists.isNotEmpty) {
                                        final target = _lists.first;
                                        await ApiService.instance.addItem(target.id, item.name);
                                        if (mounted) {
                                          messenger.showSnackBar(
                                            SnackBar(content: Text('Товар "${item.name}" добавлен в список "${target.name}"')),
                                          );
                                          await refresh();
                                        }
                                      }
                                    },'''

if old_btn in content:
    content = content.replace(old_btn, new_btn)

# 3. Remove _TransferDialogButton if unused
transfer_btn_class = '''class _TransferDialogButton extends StatelessWidget {
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

if transfer_btn_class in content:
    content = content.replace(transfer_btn_class, '')

# 4. In _ListDetailsPageState: remove unused _noResultsSuggestion, _matchCatalog
content = content.replace('  static const _noResultsSuggestion = _ProductSuggestion.empty();\n', '')

match_catalog_code = '''  List<_ProductSuggestion> _matchCatalog(String query) {
    final normalized = _normalizeQuery(query);
    if (normalized.isEmpty) return const [];
    final results = <_ProductSuggestion>[];
    for (var i = 0; i < _baseProductsRu.length; i++) {
      final ru = _baseProductsRu[i];
      final en = _baseProductsEn[i];
      final aliases = _aliases[i];
      final matches = <String>[ru, en, ...aliases]
          .map(_normalizeQuery)
          .any((value) => value.contains(normalized));
      if (matches) results.add(_ProductSuggestion(ru: ru, en: en));
    }
    return results;
  }'''

if match_catalog_code in content:
    content = content.replace(match_catalog_code, '')

# 5. In Switch: change activeColor to activeThumbColor
content = content.replace('activeColor: _authBlue,', 'activeThumbColor: _authBlue,')

with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Cleaned up warnings in main.dart!")
