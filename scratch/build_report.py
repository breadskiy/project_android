import os
import shutil
import io
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pygments import highlight
from pygments.lexers import DartLexer
from pygments.formatters import ImageFormatter
from PIL import Image

# 1. Ensure backup of original
if not os.path.exists('отчет фронтенд_исходный.docx') and os.path.exists('отчет фронтенд.docx'):
    shutil.copyfile('отчет фронтенд.docx', 'отчет фронтенд_исходный.docx')
    print("Created backup of original report: отчет фронтенд_исходный.docx")

os.makedirs('scratch/generated_images', exist_ok=True)

def generate_code_image(code: str, filename: str) -> str:
    path = os.path.join('scratch/generated_images', filename)
    formatter = ImageFormatter(
        style='monokai',
        line_numbers=False,
        font_name='Consolas',
        font_size=15,
    )
    img_bytes = highlight(code.strip(), DartLexer(), formatter)
    img = Image.open(io.BytesIO(img_bytes))
    
    # Border & padding
    border_color = (39, 40, 34)
    new_w = img.width + 30
    new_h = img.height + 30
    new_img = Image.new('RGB', (new_w, new_h), color=border_color)
    new_img.paste(img, (15, 15))
    new_img.save(path, format='PNG')
    return path

# Define code snippets
snippets = {}

snippets['img1_theme'] = """class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SmartList',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF101418),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF10B981),
          secondary: Color(0xFF6366F1),
          surface: Color(0xFF1A212A),
        ),
        cardTheme: CardTheme(
          color: const Color(0xFF1A212A),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
      ),
      home: const _AppBackdrop(child: LoginPage()),
    );
  }
}"""

snippets['img2_api'] = """class ApiService {
  static final ApiService instance = ApiService._();
  String? _accessToken;
  String? _refreshToken;

  Future<http.Response> _send(http.Request request) async {
    final streamedResponse = await request.send().timeout(const Duration(seconds: 15));
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode == 401 && _refreshToken != null) {
      final renewed = await _doRefreshToken();
      if (renewed) {
        request.headers['Authorization'] = 'Bearer $_accessToken';
        return http.Response.fromStream(await request.send());
      }
    }
    return response;
  }
}"""

snippets['img3_login'] = """Future<void> _login() async {
  if (!_formKey.currentState!.validate()) return;
  setState(() => _isLoading = true);

  final login = _loginController.text.trim();
  final password = _passwordController.text.trim();

  try {
    final user = await ApiService.instance.login(
      loginOrEmail: login,
      password: password,
    );

    if (!mounted) return;
    setState(() => _isLoading = false);

    Navigator.pushReplacement(
      context,
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 350),
        pageBuilder: (_, animation, secondaryAnimation) => FadeTransition(
          opacity: animation,
          child: HomeShell(
            login: user.displayName.isNotEmpty ? user.displayName : login,
            password: password,
          ),
        ),
      ),
    );
  } catch (e) {
    if (!mounted) return;
    setState(() => _isLoading = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
  }
}"""

snippets['img4_validation'] = """Widget _buildLoginField() {
  return TextFormField(
    controller: _loginController,
    style: const TextStyle(color: Colors.white),
    decoration: const InputDecoration(
      labelText: 'Логин или Email',
      prefixIcon: Icon(Icons.person_outline),
    ),
    validator: (value) {
      if (value == null || value.trim().isEmpty) {
        return 'Пожалуйста, введите логин или email';
      }
      if (value.trim().length < 3) {
        return 'Минимум 3 символа';
      }
      return null;
    },
  );
}"""

snippets['img5_register'] = """Future<void> _register() async {
  if (!_formKey.currentState!.validate()) return;
  setState(() => _isSaving = true);

  final login = _loginController.text.trim();
  final password = _passwordController.text.trim();
  final displayName = '${_nameController.text.trim()} ${_surnameController.text.trim()}'.trim();

  try {
    final user = await ApiService.instance.register(
      loginOrEmail: login,
      password: password,
      displayName: displayName.isNotEmpty ? displayName : login,
    );

    if (!mounted) return;
    setState(() => _isSaving = false);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Регистрация прошла успешно')),
    );

    Navigator.pushReplacement(
      context,
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 350),
        pageBuilder: (_, animation, secondaryAnimation) => FadeTransition(
          opacity: animation,
          child: HomeShell(
            login: user.displayName.isNotEmpty ? user.displayName : login,
            password: password,
          ),
        ),
      ),
    );
  } catch (e) {
    if (!mounted) return;
    setState(() => _isSaving = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
  }
}"""

snippets['img6_shell'] = """class _HomeShellState extends State<HomeShell> {
  int _selectedIndex = 0;

  void _setTab(int index) {
    if (_selectedIndex != index) {
      setState(() => _selectedIndex = index);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tabs = [
      _HomeTab(onNavigateTab: _setTab, userName: widget.login),
      const _SearchTab(),
      const ListsPage(),
      _ProfileTab(userName: widget.login),
    ];

    return Scaffold(
      body: IndexedStack(index: _selectedIndex, children: tabs),
      bottomNavigationBar: CustomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: _setTab,
        items: const [
          NavItem(icon: Icons.dashboard_outlined, label: 'Главная'),
          NavItem(icon: Icons.search_rounded, label: 'Каталог'),
          NavItem(icon: Icons.checklist_rounded, label: 'Списки'),
          NavItem(icon: Icons.person_outline_rounded, label: 'Профиль'),
        ],
      ),
    );
  }
}"""

snippets['img7_home_load'] = """Future<void> _loadData() async {
  setState(() => _isLoading = true);
  try {
    final results = await Future.wait([
      ApiService.instance.getLists(),
      ApiService.instance.getReplenish(),
      ApiService.instance.getCategories(),
    ]);

    final rawLists = results[0] as List<ApiShoppingList>;
    final replenish = results[1] as List<ApiReplenishItem>;
    final categories = results[2] as List<ApiCategory>;

    if (!mounted) return;
    setState(() {
      _lists = rawLists.map((l) => _ShoppingList.fromApi(l)).toList();
      _replenishItems = replenish;
      _categories = categories;
      _isLoading = false;
    });
  } catch (e) {
    if (mounted) setState(() { _errorMessage = e.toString(); _isLoading = false; });
  }
}"""

snippets['img8_search'] = """Future<void> _search(String query) async {
  if (query.trim().isEmpty) {
    setState(() { _searchResults = []; _isSearching = false; });
    return;
  }
  setState(() => _isSearching = true);
  try {
    final results = await ApiService.instance.searchCatalog(query.trim());
    if (!mounted) return;
    setState(() {
      _searchResults = results;
      _isSearching = false;
    });
  } catch (e) {
    if (mounted) setState(() => _isSearching = false);
  }
}

Future<void> _addWithPicker(String productName) async {
  final targetList = await _showListPickerDialog();
  if (targetList == null) return;
  await ApiService.instance.addItem(targetList.id, productName, quantity: 1.0);
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text('Товар добавлен в "${targetList.name}"')),
  );
}"""

snippets['img9_lists'] = """List<_ShoppingList> _filtered() {
  final q = _normalizeQuery(_queryController.text);
  final visible = _showAddedLists
      ? _lists.where((l) => !l.isOwner && l.role != 'owner').toList()
      : _lists.where((l) => l.isOwner || l.role == 'owner').toList();
  if (q.isEmpty) return visible;
  return visible.where((l) => _normalizeQuery(l.name).contains(q)).toList();
}

Future<void> _showJoinDialog() async {
  final codeController = TextEditingController();
  final code = await showDialog<String>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Подключиться к списку'),
      content: TextField(
        controller: codeController,
        decoration: const InputDecoration(hintText: 'Введите 6-значный инвайт-код'),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
        ElevatedButton(onPressed: () => Navigator.pop(ctx, codeController.text.trim()), child: const Text('Войти')),
      ],
    ),
  );
  if (code != null && code.isNotEmpty) {
    await ApiService.instance.joinList(code);
    await refresh();
  }
}"""

snippets['img10_add_item'] = """Future<void> _addItemWithText(String text) async {
  if (_isAddingItem) return;
  _isAddingItem = true;
  try {
    ApiParsedItem? parsed;
    try {
      parsed = await ApiService.instance.parseItem(text);
    } catch (_) {}

    final itemName = (parsed?.name.isNotEmpty == true) ? parsed!.name : text;
    final quantity = parsed?.quantity ?? 1.0;
    final unit = parsed?.unit;

    final res = await ApiService.instance.addItem(
      widget.listId,
      itemName,
      quantity: quantity,
      unit: unit,
    );
    final newItem = _ShoppingItem.fromApi(res.item);
    if (!mounted) return;
    setState(() {
      _list = _list?.copyWith(items: [newItem, ...?_list?.items]);
      _suggestions = res.suggestions;
    });
  } catch (e) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
  } finally {
    _isAddingItem = false;
  }
}"""

snippets['img11_toggle_item'] = """Future<void> _toggleItem(int index, bool? value) async {
  final current = _list;
  if (current == null || index >= current.items.length) return;
  final item = current.items[index];
  final targetChecked = value ?? !item.isDone;

  try {
    final updated = await ApiService.instance.updateItem(
      widget.listId,
      item.id,
      checked: targetChecked,
    );
    if (!mounted) return;
    final items = [...current.items];
    items[index] = _ShoppingItem.fromApi(updated);
    setState(() => _list = current.copyWith(items: items));
  } catch (e) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
  }
}"""

snippets['img12_sessions'] = """Future<void> _showSessionsSheet() async {
  final sessions = await ApiService.instance.getSessions();
  if (!mounted) return;

  showModalBottomSheet(
    context: context,
    builder: (ctx) => ListView.builder(
      itemCount: sessions.length,
      itemBuilder: (ctx, i) {
        final s = sessions[i];
        return ListTile(
          leading: Icon(s.isCurrent ? Icons.phone_android : Icons.laptop),
          title: Text(s.deviceInfo),
          subtitle: Text('IP: ${s.ipAddress} • ${s.lastActive}'),
          trailing: s.isCurrent
              ? const Chip(label: Text('Текущее'))
              : IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.red),
                  onPressed: () async {
                    await ApiService.instance.terminateSession(s.id);
                    Navigator.pop(ctx);
                  },
                ),
        );
      },
    ),
  );
}"""

snippets['img13_model'] = """class _ShoppingItem {
  final String id;
  final String name;
  final bool isDone;
  final DateTime createdAt;
  final double quantity;
  final String? unit;
  final String? notes;

  factory _ShoppingItem.fromApi(ApiShoppingItem apiItem) {
    return _ShoppingItem._(
      id: apiItem.id,
      name: apiItem.name,
      isDone: apiItem.checked,
      createdAt: apiItem.addedAt,
      quantity: apiItem.quantity,
      unit: apiItem.unit,
      notes: apiItem.notes,
    );
  }

  _ShoppingItem copyWith({
    String? id,
    String? name,
    bool? isDone,
    DateTime? createdAt,
    double? quantity,
    String? unit,
    String? notes,
  }) {
    return _ShoppingItem._(
      id: id ?? this.id,
      name: name ?? this.name,
      isDone: isDone ?? this.isDone,
      createdAt: createdAt ?? this.createdAt,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      notes: notes ?? this.notes,
    );
  }
}"""

# Generate images
img_files = {}
for name, code in snippets.items():
    img_files[name] = generate_code_image(code, f"{name}.png")
print("All code images generated.")

# Create Document
doc = docx.Document()

# Configure page setup to Russian Standard A4 (Left 30mm, Right 15mm, Top 20mm, Bottom 20mm)
section = doc.sections[0]
section.page_width = Inches(8.27)
section.page_height = Inches(11.69)
section.left_margin = Inches(1.18)   # 30 mm
section.right_margin = Inches(0.59)  # 15 mm
section.top_margin = Inches(0.79)    # 20 mm
section.bottom_margin = Inches(0.79) # 20 mm

# Base style
style_normal = doc.styles['Normal']
style_normal.font.name = 'Times New Roman'
style_normal.font.size = Pt(12)
style_normal.font.color.rgb = RGBColor(0, 0, 0)

def add_h1(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(14)
    run.bold = True
    return p

def add_h2(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(13)
    run.bold = True
    return p

def add_h3(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    run.bold = True
    return p

def add_body(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    return p

def add_desc_header():
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run("Описание:")
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    run.bold = True
    return p

def add_bullet(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.left_indent = Inches(0.25)
    run = p.add_run("•  " + text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(12)
    return p

def add_image_box(img_key, width_in=5.8):
    path = img_files[img_key]
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Inches(width_in))

# BUILD DOCUMENT CONTENT
add_h1("1. Реализованный функционал и техническая реализация")
add_body("В данном разделе приведено детальное описание архитектуры и реализованного функционала клиентской части мобильного приложения SmartList (фреймворк Flutter / язык Dart) с подробным разбором ключевых механизмов работы, структуры интерфейсов, сетевого взаимодействия с REST API бэкендом, кэширования и моделей данных.")

# 1.1
add_h2("1.1 Архитектура приложения и глобальная визуальная тема (MyApp, _AppBackdrop)")
add_body("Точка входа приложения инициализирует асинхронные службы Flutter и запускает корневой виджет MyApp. Приложение разработано в парадигме Material 3 с глубокой кастомизацией цветовой палитры и стилей.")
add_h3("Конфигурация темы и фоновая подложка")
add_image_box('img1_theme', width_in=5.8)
add_desc_header()
add_bullet("Инициализация глобальной конфигурации приложения через MaterialApp")
add_bullet("Применение темной дизайн-системы с фирменными оттенками: фоновый глубокий цвет (#101418), акцентный изумрудный (#10B981) и вторичный индиго (#6366F1)")
add_bullet("Кастомизация CardTheme с радиусом скругления углов 20dp для современного облика карточек")
add_bullet("Внедрение фонового виджета _AppBackdrop с мягким радиальным свечением для создания глубины интерфейса")

# 1.2
add_h2("1.2 Сетевой уровень и интеграция с API (ApiService)")
add_body("Взаимодействие с серверной частью вынесено в изолированный сервисный слой ApiService, реализованный по шаблону Singleton. Сервис управляет всеми HTTP-запросами и жизненным циклом пользовательской сессии.")
add_h3("Управление токенами и перехват запросов")
add_image_box('img2_api', width_in=5.8)
add_desc_header()
add_bullet("Централизованное сохранение JWT-токенов (access_token и refresh_token) в локальном хранилище SharedPreferences")
add_bullet("Автоматическое включение заголовка авторизации Authorization: Bearer <token> в каждый сетевой запрос")
add_bullet("Перехват статуса ответа 401 Unauthorized с автоматическим вызовом процедуры обновления сессии (_doRefreshToken)")
add_bullet("Повторная отправка исходного запроса с новым токеном без разлогинивания пользователя")
add_bullet("Трансляция ошибок сетевого протокола и ответов бэкенда в структурированные исключения ApiException")

# 1.3
add_h2("1.3 Система аутентификации (LoginPage)")
add_body("Экран авторизации реализован на базе StatefulWidget — LoginPage, управляющего состоянием формы входа, валидацией пользовательского ввода и анимацией интерфейса.")
add_h3("Основная функция входа")
add_image_box('img3_login', width_in=5.8)
add_desc_header()
add_bullet("Валидация корректности заполнения формы через _formKey.currentState.validate()")
add_bullet("Установка реактивного состояния загрузки (_isLoading = true) с блокировкой повторных кликов")
add_bullet("Асинхронный вызов ApiService.instance.login() с передачей логина и пароля")
add_bullet("При успешном ответе — сохранение сессии и плавный переход на HomeShell с анимацией FadeTransition")
add_bullet("Обработка исключений с выводом понятного уведомления об ошибке через SnackBar")

add_h3("Валидация полей входа")
add_image_box('img4_validation', width_in=5.8)
add_desc_header()
add_bullet("Проверка на непустое значение с удалением краевых пробелов (trim)")
add_bullet("Проверка минимально допустимой длины идентификатора (не менее 3 символов)")
add_bullet("Динамический возврат локализованной строки ошибки для отображения в поле ввода")

# 1.4
add_h2("1.4 Регистрация пользователя (RegisterPage)")
add_body("Регистрация новых учетных записей вынесена в экран RegisterPage с проверкой форматов данных и мгновенным созданием профиля на сервере.")
add_h3("Основная функция регистрации")
add_image_box('img5_register', width_in=5.8)
add_desc_header()
add_bullet("Валидация полей имени, фамилии, email/логина и пароля")
add_bullet("Контроль совпадения пароля и его повторного подтверждения")
add_bullet("Отправка запроса на регистрацию нового аккаунта через ApiService.instance.register()")
add_bullet("Отображение всплывающего уведомления об успешном создании учетной записи")
add_bullet("Автоматический вход и перенаправление в приложение без необходимости ручного повторного ввода")

# 1.5
add_h2("1.5 Навигационная оболочка приложения (HomeShell)")
add_body("Главным контейнером приложения после входа является HomeShell, реализующий постоянную нижнюю навигационную панель и сохранение состояния страниц.")
add_h3("Управление экранами и переключение вкладок")
add_image_box('img6_shell', width_in=5.8)
add_desc_header()
add_bullet("Использование IndexedStack для сохранения состояния каждого экрана при переключении")
add_bullet("Интеграция 4 основных разделов: Главный дашборд, Поиск и каталог, Реестр списков, Личный профиль")
add_bullet("Кастомная нижняя панель навигации с визуальным выделением активной вкладки")
add_bullet("Мягкая вибрационная и визуальная обратная связь при переходе между разделами")

# 1.6
add_h2("1.6 Главная страница и предиктивные рекомендации (_HomeTab)")
add_body("Главная страница служит персональной сводкой активности пользователя, объединяя списки покупок, рекомендации к покупке и популярные категории.")
add_h3("Загрузка сводных данных и аналитика пополнения")
add_image_box('img7_home_load', width_in=5.8)
add_desc_header()
add_bullet("Параллельная асинхронная загрузка данных через Future.wait: списки, прогноз пополнения и категории")
add_bullet("Блок умных рекомендаций к пополнению (Replenish Suggestions) на основе периодичности покупок")
add_bullet("Интерактивная сетка товарных категорий для быстрого добавления товаров")
add_bullet("Диалог оперативного создания нового списка покупок с выбором параметров")

# 1.7
add_h2("1.7 Поиск и каталог товаров (_SearchTab)")
add_body("Раздел поиска обеспечивает сквозной поиск по глобальному каталогу товаров с возможностью выбора списка для добавления позиции.")
add_h3("Поиск по каталогу и быстрое добавление")
add_image_box('img8_search', width_in=5.8)
add_desc_header()
add_bullet("Живой поиск с фильтрацией результатов по введенной строке на стороне сервера")
add_bullet("Отображение товарных позиций в виде карточек с категориями и ценовыми ориентирами")
add_bullet("Функция _addWithPicker() для выбора целевого списка покупок через всплывающий диалог")
add_bullet("Мгновенная отправка позиции в выбранный список и уведомление пользователя")

# 1.8
add_h2("1.8 Управление списками и совместный доступ (ListsPage)")
add_body("Экран ListsPage предоставляет полный реестр списков покупок с разделением прав доступа и возможностью совместной работы.")
add_h3("Фильтрация списков и подключение по инвайт-коду")
add_image_box('img9_lists', width_in=5.8)
add_desc_header()
add_bullet("Разделение списков по вкладкам: собственные списки и списки с совместным доступом")
add_bullet("Полнотекстовая клиентская фильтрация списка по введенному запросу")
add_bullet("Карточки списков с прогресс-баром (соотношение купленных и общих позиций) и бейджами соавторов")
add_bullet("Генерация 6-значных инвайт-кодов для предоставления совместного доступа семье и коллегам")
add_bullet("Диалог подключения к чужому списку по инвайт-коду через ApiService.instance.joinList()")

# 1.9
add_h2("1.9 Детальный экран списка покупок (ListDetailsPage)")
add_body("Основной экран работы с покупками ListDetailsPage содержит интеллектуальный ввод, динамическое обновление статусов и контекстные подсказки.")
add_h3("Умное добавление товаров с распознаванием текста")
add_image_box('img10_add_item', width_in=5.8)
add_desc_header()
add_bullet("Автоматический парсинг естественного текста (например, «Молоко 2л», «Бананы 1.5 кг»)")
add_bullet("Извлечение названия, количества и единиц измерения с обращением к ApiService.instance.parseItem()")
add_bullet("Отображение баннера рекомендаций сопутствующих товаров для быстрого добавления в один клик")
add_bullet("Реактивное включение нового элемента в начало списка с обновлением состояния")

add_h3("Управление статусом элементов")
add_image_box('img11_toggle_item', width_in=5.8)
add_desc_header()
add_bullet("Переключение состояния элемента (куплен / активен)")
add_bullet("Асинхронная фиксация статуса на бэкенде через ApiService.instance.updateItem()")
add_bullet("Анимация вычеркивания текста и полупрозрачности выполненного товара")
add_bullet("Поддержка удаления элементов свайпом (Dismissible) и групповая очистка списка")

# 1.10
add_h2("1.10 Профиль пользователя, настройки и безопасность (_ProfileTab)")
add_body("Раздел профиля предоставляет средства контроля учетной записи, изменения пароля, переключения функций ИИ и аудита активных сессий.")
add_h3("Аудит и управление активными сессиями устройств")
add_image_box('img12_sessions', width_in=5.8)
add_desc_header()
add_bullet("Отображение списка всех авторизованных клиентских устройств, IP-адресов и времени активности")
add_bullet("Возможность удаленного завершения подозрительной сессии через ApiService.instance.terminateSession()")
add_bullet("Диалог смены пароля с валидацией текущих и новых учетных данных")
add_bullet("Процедура выхода из системы (Logout) с отзывом токенов и очисткой локальной памяти")

# 1.11
add_h2("1.11 Модель данных элемента списка (_ShoppingItem)")
add_body("Для обеспечения строгой типизации данных в приложении используется специализированная модель _ShoppingItem, поддерживающая иммутабельность.")
add_h3("Структура модели и методы преобразования")
add_image_box('img13_model', width_in=5.8)
add_desc_header()
add_bullet("Хранение ключевых атрибутов: уникальный идентификатор, название, статус выполнения, количество, единицы и заметки")
add_bullet("Фабричный конструктор fromApi для трансформации серверного DTO в локальную модель")
add_bullet("Поддержка сериализации в JSON-формат для кэширования")
add_bullet("Паттерн copyWith для создания модифицированных копий без мутации исходного объекта")

# ВЫВОД
add_h1("Вывод")
add_body("В ходе разработки реализована комплексная, масштабируемая клиентская архитектура мобильного приложения SmartList на базе Flutter/Dart, включающая:")
add_bullet("Надежную систему аутентификации и регистрации с безопасным хранением JWT-токенов в SharedPreferences")
add_bullet("Изолированный сетевой сервисный слой ApiService с автоматическим обновлением токенов (refresh token) и перехватом ошибок")
add_bullet("Многоэкранную навигацию на базе IndexedStack и HomeShell со стилизованной панелью быстрого доступа")
add_bullet("Интеллектуальный ввод покупок с распознаванием наименования, единиц измерения и объема товаров")
add_bullet("Предиктивную аналитику пополнения запасов и рекомендации сопутствующих товаров")
add_bullet("Систему совместного доступа к спискам покупок на основе инвайт-кодов")
add_bullet("Аудит сессий устройств и средства управления безопасностью профиля")
add_bullet("Современный пользовательский интерфейс по стандартам Material 3 с темной темой и высокой отзывчивостью")
add_body("Реализация полностью готова к публикации на мобильных платформах (Android, iOS) и демонстрирует высокую отказоустойчивость при взаимодействии с серверным API.")

# Save both as 'отчет фронтенд.docx' and 'отчет_фронтенд_новый.docx'
doc.save('отчет фронтенд.docx')
doc.save('отчет_фронтенд_новый.docx')
print("Successfully generated and saved отчет фронтенд.docx and отчет_фронтенд_новый.docx")
