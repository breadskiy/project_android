import os

main_file = r'd:\project_android\lib\main.dart'

with open(main_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update _SearchTabState autocomplete
old_search_autocomplete = '''                Autocomplete<_ProductSuggestion>(
                  optionsBuilder: (TextEditingValue value) {
                    final query = value.text.trim();
                    if (query.isEmpty) return const Iterable<_ProductSuggestion>.empty();
                    final matches = _match(query);
                    if (matches.isEmpty) return const <_ProductSuggestion>[_noResultsSuggestion];
                    return matches;
                  },
                  onSelected: _addSuggestion,
                  fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
                    controller.value = _controller.value;
                    return TextField(
                      controller: _controller,
                      focusNode: _focusNode,
                      textInputAction: TextInputAction.search,
                      keyboardType: TextInputType.text,
                      textCapitalization: TextCapitalization.sentences,
                      onSubmitted: (_) {
                        final results = _match(_controller.text);
                        if (results.isNotEmpty) _addSuggestion(results.first);
                      },
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
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(22),
                          borderSide: const BorderSide(color: _authBlue, width: 1.5),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(22),
                          borderSide: const BorderSide(color: _authBlue, width: 2),
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

new_search_autocomplete = '''                Autocomplete<ApiCatalogProduct>(
                  optionsBuilder: (TextEditingValue value) async {
                    final query = value.text.trim();
                    if (query.isEmpty) return const Iterable<ApiCatalogProduct>.empty();
                    try {
                      final products = await ApiService.instance.searchCatalog(query);
                      return products;
                    } catch (_) {
                      return const Iterable<ApiCatalogProduct>.empty();
                    }
                  },
                  displayStringForOption: (option) => option.name,
                  onSelected: (product) => _addWithPicker(product.name),
                  fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
                    controller.value = _controller.value;
                    return TextField(
                      controller: _controller,
                      focusNode: _focusNode,
                      textInputAction: TextInputAction.search,
                      keyboardType: TextInputType.text,
                      textCapitalization: TextCapitalization.sentences,
                      onSubmitted: (v) {
                        if (v.trim().isNotEmpty) {
                          _addWithPicker(v.trim());
                        }
                      },
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
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(22),
                          borderSide: const BorderSide(color: _authBlue, width: 1.5),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(22),
                          borderSide: const BorderSide(color: _authBlue, width: 2),
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
                          constraints: const BoxConstraints(maxHeight: 280),
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

assert old_search_autocomplete in content, "Could not find old_search_autocomplete"
content = content.replace(old_search_autocomplete, new_search_autocomplete, 1)

# 2. Update _ListsPageState
old_lists_methods = '''  Future<void> _showTransferMethodDialog() async {
    await showDialog<void>(
      context: context,
      barrierColor: Colors.black54,
      builder: (context) {
        return Dialog(
          backgroundColor: Colors.transparent,
          insetPadding: const EdgeInsets.symmetric(horizontal: 42),
          child: Container(
            padding: const EdgeInsets.fromLTRB(28, 46, 28, 46),
            decoration: BoxDecoration(
              color: _authBg,
              borderRadius: BorderRadius.circular(26),
              border: Border.all(color: _authBlue, width: 2),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Выберите способ',
                  style: GoogleFonts.inter(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 36),
                _TransferDialogButton(
                  label: 'Ссылка',
                  onPressed: () {
                    Navigator.pop(context);
                    _showLinkDialog();
                  },
                ),
                const SizedBox(height: 18),
                _TransferDialogButton(
                  label: 'QR код',
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _showLinkDialog() async {
    final controller = TextEditingController();
    await showDialog<void>(
      context: context,
      barrierColor: Colors.black54,
      builder: (context) {
        return Dialog(
          backgroundColor: Colors.transparent,
          insetPadding: const EdgeInsets.symmetric(horizontal: 48),
          child: Container(
            padding: const EdgeInsets.fromLTRB(28, 46, 28, 46),
            decoration: BoxDecoration(
              color: _authBg,
              borderRadius: BorderRadius.circular(26),
              border: Border.all(color: _authBlue, width: 2),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Ссылка',
                  style: GoogleFonts.inter(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: controller,
                  style: GoogleFonts.inter(
                    color: _ink,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                  decoration: InputDecoration(
                    isDense: true,
                    filled: true,
                    fillColor: Colors.white,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 10,
                    ),
                    hintText: '',
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: _authBlue, width: 2),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: _authBlue, width: 2),
                    ),
                  ),
                ),
                const SizedBox(height: 28),
                Center(
                  child: SizedBox(
                    width: 124,
                    height: 42,
                    child: ElevatedButton(
                      onPressed: () => Navigator.pop(context),
                      style: ElevatedButton.styleFrom(
                        elevation: 0,
                        backgroundColor: _authBlueDark,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(22),
                        ),
                      ),
                      child: Text(
                        'Отправить',
                        style: GoogleFonts.inter(
                          fontWeight: FontWeight.w800,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
    controller.dispose();
  }'''

new_lists_methods = '''  Future<void> _showShareDialog(_ShoppingList list) async {
    if (list.isSystem) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Системный список («⭐ Избранное») нельзя опубликовать')),
      );
      return;
    }

    showDialog<void>(
      context: context,
      barrierColor: Colors.black54,
      builder: (context) {
        return FutureBuilder<ApiInviteInfo>(
          future: ApiService.instance.createInvite(list.id),
          builder: (context, snapshot) {
            return Dialog(
              backgroundColor: Colors.transparent,
              insetPadding: const EdgeInsets.symmetric(horizontal: 28),
              child: Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: _authCard,
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: _authBlue, width: 2),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Поделиться списком',
                      style: GoogleFonts.inter(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      list.name,
                      style: const TextStyle(color: Colors.white70, fontSize: 14),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 20),
                    if (snapshot.connectionState == ConnectionState.waiting)
                      const Padding(
                        padding: EdgeInsets.all(24),
                        child: CircularProgressIndicator(color: _authBlue),
                      )
                    else if (snapshot.hasError)
                      Padding(
                        padding: const EdgeInsets.all(12),
                        child: Text(
                          'Ошибка: ${snapshot.error}',
                          style: const TextStyle(color: _danger),
                          textAlign: TextAlign.center,
                        ),
                      )
                    else if (snapshot.hasData) ...[
                      const Text(
                        'Код приглашения:',
                        style: TextStyle(color: Colors.white54, fontSize: 13),
                      ),
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.35),
                          borderRadius: BorderRadius.circular(14),
                          border: Border.all(color: _authBlue.withValues(alpha: 0.5)),
                        ),
                        child: SelectableText(
                          snapshot.data!.code,
                          style: GoogleFonts.robotoMono(
                            color: Colors.white,
                            fontSize: 22,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 3,
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: snapshot.data!.code));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Код скопирован в буфер обмена!')),
                          );
                        },
                        icon: const Icon(Icons.copy, size: 18),
                        label: const Text('Скопировать код'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _authBlue,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextButton.icon(
                        onPressed: () {
                          Clipboard.setData(ClipboardData(text: snapshot.data!.link));
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Ссылка скопирована в буфер обмена!')),
                          );
                        },
                        icon: const Icon(Icons.link, size: 18),
                        label: const Text('Скопировать ссылку'),
                        style: TextButton.styleFrom(foregroundColor: Colors.white70),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Закрыть', style: TextStyle(color: Colors.white60)),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _showJoinDialog() async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          title: const Text('Присоединиться к списку', style: TextStyle(color: Colors.white)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Введите код приглашения (из 8+ символов):',
                style: TextStyle(color: Colors.white70, fontSize: 13),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                autofocus: true,
                textCapitalization: TextCapitalization.characters,
                style: GoogleFonts.robotoMono(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 2,
                ),
                decoration: InputDecoration(
                  hintText: 'Например: K7M2QXJ4',
                  hintStyle: const TextStyle(color: Colors.white38, letterSpacing: 1),
                  filled: true,
                  fillColor: Colors.black.withValues(alpha: 0.25),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: const BorderSide(color: _authBlue, width: 1.5),
                  ),
                ),
              ),
            ],
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
              child: const Text('Присоединиться'),
            ),
          ],
        );
      },
    );

    if (result != null && result.isNotEmpty) {
      try {
        final joined = await ApiService.instance.joinList(result);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Вы присоединились к списку "${joined.name}"!')),
        );
        await refresh();
        if (mounted && joined.id.isNotEmpty) {
          await _openList(_ShoppingList.fromApi(joined));
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Не удалось присоединиться: $e')),
          );
        }
      }
    }
  }

  Future<void> _showReplenishDialog() async {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) {
        return Container(
          decoration: BoxDecoration(
            color: _authCard,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            border: Border.all(color: _authBlue.withValues(alpha: 0.4), width: 1.5),
          ),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: SafeArea(
            top: false,
            child: FutureBuilder<List<ApiReplenishItem>>(
              future: ApiService.instance.getReplenish(),
              builder: (context, snapshot) {
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 44,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.white24,
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        const Icon(Icons.auto_awesome, color: _authBlue, size: 22),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Что скоро закончится',
                            style: GoogleFonts.inter(
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        IconButton(
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.close, color: Colors.white60, size: 20),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Система анализирует историю покупок и рассчитывает, какие товары пора докупить.',
                      style: TextStyle(color: Colors.white60, fontSize: 13),
                    ),
                    const SizedBox(height: 16),
                    if (snapshot.connectionState == ConnectionState.waiting)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 36),
                        child: Center(
                          child: CircularProgressIndicator(color: _authBlue),
                        ),
                      )
                    else if (snapshot.hasError)
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(
                          'Ошибка: ${snapshot.error}',
                          style: const TextStyle(color: _danger),
                        ),
                      )
                    else if (snapshot.data == null || snapshot.data!.isEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 24),
                        child: Column(
                          children: [
                            Icon(Icons.checklist, size: 48, color: Colors.white.withValues(alpha: 0.2)),
                            const SizedBox(height: 12),
                            const Text(
                              'Пока нет товаров для пополнения',
                              style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                            ),
                            const SizedBox(height: 6),
                            const Text(
                              'Отмечайте купленные товары в списках покупок (не менее 3 раз), чтобы алгоритм рассчитал регулярность и сформировал прогноз.',
                              style: TextStyle(color: Colors.white60, fontSize: 12),
                              textAlign: TextAlign.center,
                            ),
                          ],
                        ),
                      )
                    else
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxHeight: 340),
                        child: ListView.separated(
                          shrinkWrap: true,
                          itemCount: snapshot.data!.length,
                          separatorBuilder: (_, _) => const SizedBox(height: 10),
                          itemBuilder: (context, index) {
                            final item = snapshot.data![index];
                            return Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(color: _authBlue, width: 1.4),
                              ),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          item.name,
                                          style: const TextStyle(
                                            color: _ink,
                                            fontWeight: FontWeight.w700,
                                            fontSize: 14,
                                          ),
                                        ),
                                        const SizedBox(height: 3),
                                        Text(
                                          'Интервал: ~${item.avgIntervalDays.toStringAsFixed(0)} дн. (прошло ${item.daysSinceLast.toStringAsFixed(0)} дн.)',
                                          style: const TextStyle(color: _muted, fontSize: 11),
                                        ),
                                      ],
                                    ),
                                  ),
                                  ElevatedButton.icon(
                                    onPressed: () async {
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
                                    },
                                    icon: const Icon(Icons.add, size: 16),
                                    label: const Text('Добавить', style: TextStyle(fontSize: 12)),
                                    style: ElevatedButton.styleFrom(
                                      backgroundColor: _authBlue,
                                      foregroundColor: Colors.white,
                                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                      visualDensity: VisualDensity.compact,
                                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                                    ),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                      ),
                  ],
                );
              },
            ),
          ),
        );
      },
    );
  }'''

assert old_lists_methods in content, "Could not find old_lists_methods"
content = content.replace(old_lists_methods, new_lists_methods, 1)

# 3. Update list card in _ListsPageState to pass list to share and handle delete
old_card_actions = '''              IconButton(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints.tightFor(width: 28, height: 34),
                onPressed: _showTransferMethodDialog,
                icon: const Icon(Icons.ios_share_outlined, size: 21),
                color: _authBlue,
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints.tightFor(width: 28, height: 34),
                onPressed: () => _toggleFavorite(list),
                icon: Icon(
                  list.isFavorite ? Icons.favorite : Icons.favorite_border,
                  size: 22,
                ),
                color: _authBlue,
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints.tightFor(width: 28, height: 34),
                onPressed: () => _deleteList(list),
                icon: const Icon(Icons.delete_outline, size: 22),
                color: _authBlue,
              ),'''

new_card_actions = '''              IconButton(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints.tightFor(width: 28, height: 34),
                onPressed: () => _showShareDialog(list),
                icon: const Icon(Icons.ios_share_outlined, size: 21),
                color: _authBlue,
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints.tightFor(width: 28, height: 34),
                onPressed: () => _toggleFavorite(list),
                icon: Icon(
                  list.isFavorite ? Icons.favorite : Icons.favorite_border,
                  size: 22,
                ),
                color: _authBlue,
              ),
              if (!list.isSystem)
                IconButton(
                  visualDensity: VisualDensity.compact,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints.tightFor(width: 28, height: 34),
                  onPressed: () => _deleteList(list),
                  icon: const Icon(Icons.delete_outline, size: 22),
                  color: _authBlue,
                ),'''

assert old_card_actions in content, "Could not find old_card_actions"
content = content.replace(old_card_actions, new_card_actions, 1)

# 4. Update _deleteList to check isSystem
old_delete_list = '''  Future<void> _deleteList(_ShoppingList list) async {
    try {
      await ApiService.instance.deleteList(list.id);
      if (!mounted) return;
      setState(() {
        _lists.removeWhere((e) => e.id == list.id);
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Не удалось удалить список: $e')),
        );
      }
    }
  }'''

new_delete_list = '''  Future<void> _deleteList(_ShoppingList list) async {
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
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Не удалось удалить список: $e')),
        );
      }
    }
  }'''

assert old_delete_list in content, "Could not find old_delete_list"
content = content.replace(old_delete_list, new_delete_list, 1)

# 5. Fix _buildListsTab in ListsPage to show added lists and join button
old_lists_view = '''                  Expanded(
                    child: _showAddedLists
                        ? const SizedBox.shrink()
                        : _isLoading
                        ? const Center(
                      child: SizedBox(
                        height: 26,
                        width: 26,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: _authBlue,
                        ),
                      ),
                    )
                        : filtered.isEmpty
                        ? const Center(
                      child: Text(
                        'Списков пока нет',
                        style: TextStyle(color: Colors.white70),
                      ),
                    )
                        : ListView.builder(
                      padding: EdgeInsets.zero,
                      itemCount: filtered.length,
                      itemBuilder: (context, index) {
                        final list = filtered[index];
                        return _buildListCard(list);
                      },
                    ),
                  ),
                  const SizedBox(height: 8),
                  if (_showAddedLists)
                    SizedBox(
                      width: 174,
                      height: 46,
                      child: ElevatedButton(
                        onPressed: _showTransferMethodDialog,
                        style: ElevatedButton.styleFrom(
                          padding: EdgeInsets.zero,
                          backgroundColor: _authBlue,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(26),
                          ),
                        ),
                        child: Text(
                          'Добавить список',
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    )
                  else
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _addListDialog,
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          backgroundColor: _authBlue,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(26),
                          ),
                        ),
                        child: const Text('Добавить список'),
                      ),
                    ),'''

new_lists_view = '''                  Expanded(
                    child: _isLoading
                        ? const Center(
                      child: SizedBox(
                        height: 26,
                        width: 26,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: _authBlue,
                        ),
                      ),
                    )
                        : filtered.isEmpty
                        ? Center(
                      child: Text(
                        _showAddedLists
                            ? 'Нет добавленных списков. Присоединяйтесь по коду!'
                            : 'Списков пока нет',
                        style: const TextStyle(color: Colors.white70),
                      ),
                    )
                        : ListView.builder(
                      padding: EdgeInsets.zero,
                      itemCount: filtered.length,
                      itemBuilder: (context, index) {
                        final list = filtered[index];
                        return _buildListCard(list);
                      },
                    ),
                  ),
                  const SizedBox(height: 8),
                  if (_showAddedLists)
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        onPressed: _showJoinDialog,
                        icon: const Icon(Icons.group_add),
                        label: Text(
                          'Присоединиться по коду',
                          style: GoogleFonts.inter(fontSize: 14, fontWeight: FontWeight.w800),
                        ),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 15),
                          backgroundColor: _authBlue,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(26),
                          ),
                        ),
                      ),
                    )
                  else
                    Row(
                      children: [
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: _addListDialog,
                            icon: const Icon(Icons.add),
                            label: const Text('Добавить список'),
                            style: ElevatedButton.styleFrom(
                              padding: const EdgeInsets.symmetric(vertical: 15),
                              backgroundColor: _authBlue,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(26),
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        ElevatedButton.icon(
                          onPressed: _showReplenishDialog,
                          icon: const Icon(Icons.auto_awesome, color: _authBlue, size: 18),
                          label: const Text('Пополнение'),
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 15),
                            backgroundColor: _authCard,
                            foregroundColor: Colors.white,
                            side: BorderSide(color: _authBlue.withValues(alpha: 0.6)),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(26),
                            ),
                          ),
                        ),
                      ],
                    ),'''

assert old_lists_view in content, "Could not find old_lists_view"
content = content.replace(old_lists_view, new_lists_view, 1)

with open(main_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Batch 1 (ListsPage and SearchTab) successfully patched!")
