main_file = r'd:\project_android\lib\main.dart'

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Restore activeColor
content = content.replace('activeThumbColor: _authBlue,', 'activeColor: _authBlue,')

# In _ProfileHomeView, ignore deprecated_member_use on Switch
content = content.replace(
    'Switch(\n                          value: aiSuggestionsEnabled,\n                          activeColor: _authBlue,',
    '// ignore: deprecated_member_use\n                        Switch(\n                          value: aiSuggestionsEnabled,\n                          activeColor: _authBlue,'
)

# Remove unused _baseProductsEn and _aliases in _SearchTabState
# And remove unused _baseProductsRu, _baseProductsEn, _aliases in _ListDetailsPageState

with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Restored activeColor!")
