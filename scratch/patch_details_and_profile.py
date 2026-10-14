import os

main_file = r'd:\project_android\lib\main.dart'

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update ListDetailsPage: _renameListDialog and _toggleFavorite
old_rename_dialog = '''  Future<void> _renameListDialog() async {
    final current = _list;
    if (current == null) return;
    final controller = TextEditingController(text: current.name);
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          title: const Text('Переименовать список', style: TextStyle(color: Colors.white)),
          content: TextField(
            controller: controller,
            autofocus: true,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: 'Новое название',
              hintStyle: const TextStyle(color: Colors.white54),
              filled: true,
              fillColor: Colors.black.withValues(alpha: 0.15),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Отмена', style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, controller.text.trim()),
              style: ElevatedButton.styleFrom(
                backgroundColor: _authBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text('Сохранить'),
            ),
          ],
        );
      },
    );
    if (result != null && result.isNotEmpty && result != current.name) {
      try {
        final updated = await ApiService.instance.updateList(widget.listId, name: result);
        if (!mounted) return;
        setState(() {
          _list = current.copyWith(name: updated.name);
        });
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  void _toggleFavorite() {
    final current = _list;
    if (current == null) return;
    setState(() {
      _list = current.copyWith(isFavorite: !current.isFavorite);
    });
  }'''

new_rename_dialog = '''  Future<void> _renameListDialog() async {
    final current = _list;
    if (current == null) return;
    if (current.isSystem) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Системный список («⭐ Избранное») нельзя переименовать')),
      );
      return;
    }
    final controller = TextEditingController(text: current.name);
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          title: const Text('Переименовать список', style: TextStyle(color: Colors.white)),
          content: TextField(
            controller: controller,
            autofocus: true,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              hintText: 'Новое название',
              hintStyle: const TextStyle(color: Colors.white54),
              filled: true,
              fillColor: Colors.black.withValues(alpha: 0.15),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Отмена', style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, controller.text.trim()),
              style: ElevatedButton.styleFrom(
                backgroundColor: _authBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text('Сохранить'),
            ),
          ],
        );
      },
    );
    if (result != null && result.isNotEmpty && result != current.name) {
      try {
        final updated = await ApiService.instance.updateList(widget.listId, name: result);
        if (!mounted) return;
        setState(() {
          _list = current.copyWith(name: updated.name);
        });
      } catch (e) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  void _toggleFavorite() {
    final current = _list;
    if (current == null) return;
    if (current.isSystem) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Этот список является системным избранным')),
      );
      return;
    }
    setState(() {
      _list = current.copyWith(isFavorite: !current.isFavorite);
    });
  }'''

assert old_rename_dialog in content, "Could not find old_rename_dialog"
content = content.replace(old_rename_dialog, new_rename_dialog, 1)

# 2. Update _showSearchAddSheet to use ApiCatalogProduct search
old_search_add_sheet = '''                  Autocomplete<_ProductSuggestion>(
                    optionsBuilder: (TextEditingValue value) {
                      final q = value.text.trim();
                      if (q.isEmpty) return const Iterable<_ProductSuggestion>.empty();
                      final matches = _matchCatalog(q);
                      if (matches.isEmpty) return const <_ProductSuggestion>[_noResultsSuggestion];
                      return matches;
                    },
                    onSelected: addSuggestion,
                    fieldViewBuilder: (context, textController, node, onFieldSubmitted) {
                      controller.value = textController.value;
                      focusNode.requestFocus();
                      return TextField(
                        controller: textController,
                        focusNode: node,
                        textInputAction: TextInputAction.search,
                        decoration: InputDecoration(
                          hintText: 'Например: milk / молоко',
                          prefixIcon: const Icon(Icons.search, color: _authBlue),
                          filled: true,
                          fillColor: Colors.white,
                          hintStyle: const TextStyle(color: Colors.black38),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(22),
                            borderSide: const BorderSide(color: _authBlue, width: 1.5),
                          ),
                        ),
                      );
                    },
                    optionsViewBuilder: (context, onSelected, options) {
                      return Align(
                        alignment: Alignment.topLeft,
                        child: Material(
                          elevation: 6,
                          borderRadius: BorderRadius.circular(16),
                          color: Colors.white,
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxHeight: 260),
                            child: ListView.separated(
                              padding: const EdgeInsets.all(8),
                              shrinkWrap: true,
                              itemCount: options.length,
                              separatorBuilder: (_, _) => const SizedBox(height: 6),
                              itemBuilder: (context, index) {
                                final option = options.elementAt(index);
                                if (option.isPlaceholder) {
                                  return const Padding(
                                    padding: EdgeInsets.all(12),
                                    child: Text(
                                      'Nothing found / Ничего не найдено',
                                      style: TextStyle(color: _muted),
                                    ),
                                  );
                                }
                                return InkWell(
                                  borderRadius: BorderRadius.circular(12),
                                  onTap: () => onSelected(option),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 10,
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.add, size: 16, color: _authBlue),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                option.ru,
                                                style: const TextStyle(
                                                  color: _ink,
                                                  fontWeight: FontWeight.w600,
                                                ),
                                              ),
                                              Text(
                                                option.en,
                                                style: const TextStyle(
                                                  color: _muted,
                                                  fontSize: 12,
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        ),
                      );
                    },
                  ),'''

new_search_add_sheet = '''                  Autocomplete<ApiCatalogProduct>(
                    optionsBuilder: (TextEditingValue value) async {
                      final q = value.text.trim();
                      if (q.isEmpty) return const Iterable<ApiCatalogProduct>.empty();
                      try {
                        final products = await ApiService.instance.searchCatalog(q);
                        return products;
                      } catch (_) {
                        return const Iterable<ApiCatalogProduct>.empty();
                      }
                    },
                    displayStringForOption: (option) => option.name,
                    onSelected: (product) async {
                      final messenger = ScaffoldMessenger.of(context);
                      Navigator.pop(context);
                      try {
                        final res = await ApiService.instance.addItem(widget.listId, product.name);
                        if (!mounted) return;
                        setState(() {
                          _list = _list?.copyWith(
                            items: [_ShoppingItem.fromApi(res.item), ...?_list?.items],
                          );
                          _suggestions = res.suggestions;
                        });
                      } catch (e) {
                        messenger.showSnackBar(SnackBar(content: Text(e.toString())));
                      }
                    },
                    fieldViewBuilder: (context, textController, node, onFieldSubmitted) {
                      controller.value = textController.value;
                      focusNode.requestFocus();
                      return TextField(
                        controller: textController,
                        focusNode: node,
                        textInputAction: TextInputAction.search,
                        decoration: InputDecoration(
                          hintText: 'Поиск по каталогу (молоко, сыр...)',
                          prefixIcon: const Icon(Icons.search, color: _authBlue),
                          filled: true,
                          fillColor: Colors.white,
                          hintStyle: const TextStyle(color: Colors.black38),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(22),
                            borderSide: const BorderSide(color: _authBlue, width: 1.5),
                          ),
                        ),
                      );
                    },
                    optionsViewBuilder: (context, onSelected, options) {
                      return Align(
                        alignment: Alignment.topLeft,
                        child: Material(
                          elevation: 6,
                          borderRadius: BorderRadius.circular(16),
                          color: Colors.white,
                          child: ConstrainedBox(
                            constraints: const BoxConstraints(maxHeight: 260),
                            child: ListView.separated(
                              padding: const EdgeInsets.all(8),
                              shrinkWrap: true,
                              itemCount: options.length,
                              separatorBuilder: (_, _) => const SizedBox(height: 6),
                              itemBuilder: (context, index) {
                                final option = options.elementAt(index);
                                return InkWell(
                                  borderRadius: BorderRadius.circular(12),
                                  onTap: () => onSelected(option),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 12,
                                      vertical: 10,
                                    ),
                                    child: Row(
                                      children: [
                                        const Icon(Icons.add, size: 16, color: _authBlue),
                                        const SizedBox(width: 8),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                option.name,
                                                style: const TextStyle(
                                                  color: _ink,
                                                  fontWeight: FontWeight.w600,
                                                ),
                                              ),
                                              if (option.categoryName != null || option.defaultUnit != null)
                                                Text(
                                                  '${option.categoryName ?? ''}${option.defaultUnit != null ? ' (${option.defaultUnit})' : ''}',
                                                  style: const TextStyle(
                                                    color: _muted,
                                                    fontSize: 12,
                                                  ),
                                                ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        ),
                      );
                    },
                  ),'''

assert old_search_add_sheet in content, "Could not find old_search_add_sheet"
content = content.replace(old_search_add_sheet, new_search_add_sheet, 1)

# 3. Update item rendering in ListDetailsPage to show quantity and unit
old_item_render = '''                                Expanded(
                                  child: Text(
                                    item.name,
                                    style: TextStyle(
                                      decoration: item.isDone
                                          ? TextDecoration.lineThrough
                                          : TextDecoration.none,
                                      color: item.isDone ? Colors.black38 : _ink,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),'''

new_item_render = '''                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        item.name,
                                        style: TextStyle(
                                          decoration: item.isDone
                                              ? TextDecoration.lineThrough
                                              : TextDecoration.none,
                                          color: item.isDone ? Colors.black38 : _ink,
                                          fontWeight: FontWeight.w600,
                                          fontSize: 14,
                                        ),
                                      ),
                                      if (item.quantity > 0 || (item.unit != null && item.unit!.isNotEmpty))
                                        Padding(
                                          padding: const EdgeInsets.only(top: 3),
                                          child: Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                            decoration: BoxDecoration(
                                              color: _authBlue.withValues(alpha: 0.12),
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                            child: Text(
                                              '${item.quantity == item.quantity.toInt() ? item.quantity.toInt() : item.quantity}${item.unit != null && item.unit!.isNotEmpty ? ' ${item.unit}' : ''}',
                                              style: GoogleFonts.inter(
                                                fontSize: 11,
                                                fontWeight: FontWeight.w700,
                                                color: _authBlueDark,
                                              ),
                                            ),
                                          ),
                                        ),
                                    ],
                                  ),
                                ),'''

assert old_item_render in content, "Could not find old_item_render"
content = content.replace(old_item_render, new_item_render, 1)

# 4. In ListDetailsPage app bar, hide/disable rename button if system list
old_app_bar_actions = '''                      IconButton(
                        onPressed: _renameListDialog,
                        icon: const Icon(Icons.edit_outlined),
                        color: Colors.white70,
                      ),'''

new_app_bar_actions = '''                      if (!current.isSystem)
                        IconButton(
                          onPressed: _renameListDialog,
                          icon: const Icon(Icons.edit_outlined),
                          color: Colors.white70,
                        ),'''

assert old_app_bar_actions in content, "Could not find old_app_bar_actions"
content = content.replace(old_app_bar_actions, new_app_bar_actions, 1)

# 5. Update _ProfileTabState to load and toggle AI settings
old_profile_tab_state = '''class _ProfileTabState extends State<_ProfileTab> {
  late final TextEditingController _nameController;
  final GlobalKey<NavigatorState> _navKey = GlobalKey<NavigatorState>();

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.login);
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }'''

new_profile_tab_state = '''class _ProfileTabState extends State<_ProfileTab> {
  late final TextEditingController _nameController;
  final GlobalKey<NavigatorState> _navKey = GlobalKey<NavigatorState>();
  ApiUserSettings? _settings;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.login);
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    try {
      final s = await ApiService.instance.getUserSettings();
      if (mounted) setState(() => _settings = s);
    } catch (_) {}
  }

  Future<void> _toggleAi(bool val) async {
    try {
      final s = await ApiService.instance.updateUserSettings(aiSuggestionsEnabled: val);
      if (mounted) setState(() => _settings = s);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Ошибка настроек: $e')));
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }'''

assert old_profile_tab_state in content, "Could not find old_profile_tab_state"
content = content.replace(old_profile_tab_state, new_profile_tab_state, 1)

# 6. Pass ai settings to _ProfileHomeView
old_home_view_call = '''            builder: (context) => _ProfileHomeView(
              login: widget.login,
              nameController: _nameController,'''

new_home_view_call = '''            builder: (context) => _ProfileHomeView(
              login: widget.login,
              nameController: _nameController,
              aiSuggestionsEnabled: _settings?.aiSuggestionsEnabled ?? true,
              onToggleAiSuggestions: _toggleAi,'''

assert old_home_view_call in content, "Could not find old_home_view_call"
content = content.replace(old_home_view_call, new_home_view_call, 1)

# 7. Update _ProfileHomeView to take ai settings and display switch
old_profile_home_view_fields = '''class _ProfileHomeView extends StatelessWidget {
  final String login;
  final TextEditingController nameController;
  final VoidCallback onHistory;
  final VoidCallback onDeleted;
  final VoidCallback onFavorites;

  const _ProfileHomeView({
    required this.login,
    required this.nameController,
    required this.onHistory,
    required this.onDeleted,
    required this.onFavorites,
  });'''

new_profile_home_view_fields = '''class _ProfileHomeView extends StatelessWidget {
  final String login;
  final TextEditingController nameController;
  final bool aiSuggestionsEnabled;
  final ValueChanged<bool> onToggleAiSuggestions;
  final VoidCallback onHistory;
  final VoidCallback onDeleted;
  final VoidCallback onFavorites;

  const _ProfileHomeView({
    required this.login,
    required this.nameController,
    required this.aiSuggestionsEnabled,
    required this.onToggleAiSuggestions,
    required this.onHistory,
    required this.onDeleted,
    required this.onFavorites,
  });'''

assert old_profile_home_view_fields in content, "Could not find old_profile_home_view_fields"
content = content.replace(old_profile_home_view_fields, new_profile_home_view_fields, 1)

# 8. Add AI switch and Replenish button in _ProfileHomeView
old_profile_actions = '''                  Container(
                    height: 2,
                    color: _authBlue,
                  ),
                  const SizedBox(height: 22),
                  _ProfileActionButton(
                    label: 'История списков',
                    onPressed: onHistory,
                  ),'''

new_profile_actions = '''                  Container(
                    height: 2,
                    color: _authBlue,
                  ),
                  const SizedBox(height: 18),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                    decoration: BoxDecoration(
                      color: _authCard,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.auto_awesome, color: _authBlue, size: 22),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Подсказки ИИ ("часто берут")',
                                style: GoogleFonts.inter(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 13,
                                ),
                              ),
                              const SizedBox(height: 2),
                              const Text(
                                'Рекомендации сопутствующих товаров при покупках',
                                style: TextStyle(color: Colors.white60, fontSize: 11),
                              ),
                            ],
                          ),
                        ),
                        Switch(
                          value: aiSuggestionsEnabled,
                          activeColor: _authBlue,
                          onChanged: onToggleAiSuggestions,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 18),
                  _ProfileActionButton(
                    label: 'История списков',
                    onPressed: onHistory,
                  ),'''

assert old_profile_actions in content, "Could not find old_profile_actions"
content = content.replace(old_profile_actions, new_profile_actions, 1)

# 9. Update _ProfileListsViewState delete and open methods
old_profile_lists_methods = '''  Future<void> _delete(_ShoppingList list) async {
    final idx = _lists.indexWhere((e) => e.id == list.id);
    if (idx < 0) return;
    setState(() {
      _lists[idx] = _lists[idx].copyWith(isDeleted: true, deletedAt: DateTime.now());
    });
    await _persist();
  }'''

new_profile_lists_methods = '''  Future<void> _openList(_ShoppingList list) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ListDetailsPage(
          listId: list.id,
          listTitle: list.name,
        ),
      ),
    );
    await _load();
  }

  Future<void> _delete(_ShoppingList list) async {
    if (list.isSystem) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Системный список («⭐ Избранное») нельзя удалить')),
      );
      return;
    }
    try {
      await ApiService.instance.deleteList(list.id);
      if (!mounted) return;
      setState(() {
        _lists.removeWhere((e) => e.id == list.id);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Список "${list.name}" удален')),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка удаления: $e')),
        );
      }
    }
  }'''

assert old_profile_lists_methods in content, "Could not find old_profile_lists_methods"
content = content.replace(old_profile_lists_methods, new_profile_lists_methods, 1)

# 10. Update onTap in _ProfileListsViewState
old_profile_ontap = 'onTap: widget.onOpenListsTab,'
new_profile_ontap = 'onTap: () => _openList(list),'
assert old_profile_ontap in content, "Could not find old_profile_ontap"
content = content.replace(old_profile_ontap, new_profile_ontap, 1)

with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Batch 2 (ListDetails, Profile, and ProfileLists) successfully patched!")
