import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:project_android/services/api_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ApiService.instance.init();
  runApp(const MyApp());
}

const _seed = Color(0xFF2D6A5A);
const _ink = Color(0xFF1F2A2E);
const _muted = Color(0xFF6B7C7F);
const _bg = Color(0xFFF8F8F6);
const _surface = Colors.white;
const _border = Color(0xFFE4E8E6);
const _danger = Color(0xFFE76F51);
const _authBg = Color(0xFF1D1D1F);
const _authCard = Color(0xFF24262B);
const _authBlue = Color(0xFF1D8CFF);
const _authBlueDark = Color(0xFF136FD1);

String _normalizeQuery(String value) {
  return value.trim().toLowerCase().replaceAll('ё', 'е');
}

/// Названия товаров показываем с большой буквы.
String capName(String value) {
  final t = value.trim();
  if (t.isEmpty) return t;
  return t[0].toUpperCase() + t.substring(1);
}

class _AppBackdrop extends StatelessWidget {
  const _AppBackdrop();

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              Color(0xFF14171B),
              Color(0xFF1D1D1F),
              Color(0xFF10243B),
            ],
          ),
        ),
        child: Stack(
          children: [
            Positioned(
              top: -80,
              left: -60,
              child: Container(
                width: 220,
                height: 220,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _authBlue.withValues(alpha: 0.18),
                ),
              ),
            ),
            Positioned(
              right: -70,
              bottom: -90,
              child: Container(
                width: 240,
                height: 240,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.tealAccent.withValues(alpha: 0.08),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: _seed,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: _bg,
    );

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Shopping List',
      theme: base.copyWith(
        textTheme: GoogleFonts.interTextTheme(base.textTheme).copyWith(
          titleLarge: GoogleFonts.inter(
            fontSize: 26,
            fontWeight: FontWeight.w600,
            color: _ink,
          ),
          titleMedium: GoogleFonts.inter(
            fontSize: 20,
            fontWeight: FontWeight.w600,
            color: _ink,
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: _surface,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: const BorderSide(color: _border),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: const BorderSide(color: _border),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: const BorderSide(color: _seed, width: 1.2),
          ),
          labelStyle: const TextStyle(color: _muted),
        ),
      ),
      home: ApiService.instance.isLoggedIn
          ? HomeShell(
              login: ApiService.instance.currentUser?.displayName ?? 'Пользователь',
              password: '',
            )
          : const LoginPage(),
    );
  }
}

class LoginPage extends StatefulWidget {
  final String? initialLogin;
  final String? initialPassword;

  const LoginPage({
    super.key,
    this.initialLogin,
    this.initialPassword,
  });

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _loginController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscure = true;
  bool _isLoading = false;

  late AnimationController _animationController;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _loginController.text = widget.initialLogin ?? '';
    _passwordController.text = widget.initialPassword ?? '';

    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );

    _fadeAnimation = CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    );

    _animationController.forward();
  }

  Future<void> _login() async {
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
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    }
  }

  @override
  void dispose() {
    _animationController.dispose();
    _loginController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          Center(
            child: FadeTransition(
              opacity: _fadeAnimation,
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 420),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _buildAuthTitle(),
                      const SizedBox(height: 10),
                      const Text(
                        'Smart groceries in one place',
                        style: TextStyle(color: Colors.white60),
                      ),
                      const SizedBox(height: 22),
                      _buildAuthCard(
                        child: Form(
                          key: _formKey,
                          child: Column(
                            children: [
                              _buildAuthLabeledField(
                                label: 'Логин',
                                child: _buildLoginField(),
                              ),
                              const SizedBox(height: 14),
                              _buildAuthLabeledField(
                                label: 'Пароль',
                                child: _buildPasswordField(),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 18),
                      _isLoading
                          ? const SizedBox(
                        height: 26,
                        width: 26,
                        child: CircularProgressIndicator(
                          color: _authBlue,
                          strokeWidth: 2.4,
                        ),
                      )
                          : _buildLoginButton(),
                      const SizedBox(height: 8),
                      TextButton(
                        onPressed: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => const RegisterPage(),
                            ),
                          );
                        },
                        child: const Text(
                          'Регистрация',
                          style: TextStyle(color: _authBlue),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoginField() {
    return TextFormField(
      controller: _loginController,
      validator: (value) {
        if (value == null || value.isEmpty) {
          return 'Введите логин';
        }
        if (value.length < 3) {
          return 'Минимум 3 символа';
        }
        return null;
      },
      decoration: const InputDecoration(
        hintText: 'IvanIvanov2000',
        prefixIcon: Icon(Icons.person_outline, color: _authBlue),
      ),
    );
  }

  Widget _buildPasswordField() {
    return TextFormField(
      controller: _passwordController,
      obscureText: _obscure,
      validator: (value) {
        if (value == null || value.length < 8) {
          return 'Пароль минимум 8 символов';
        }
        return null;
      },
      decoration: InputDecoration(
        hintText: 'Минимум 8 символов',
        prefixIcon: const Icon(Icons.lock_outline, color: _authBlue),
        suffixIcon: IconButton(
          icon: Icon(
            _obscure ? Icons.visibility : Icons.visibility_off,
            color: Colors.white54,
          ),
          onPressed: () => setState(() => _obscure = !_obscure),
        ),
      ),
    );
  }

  Widget _buildLoginButton() {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: _login,
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 16),
          backgroundColor: _authBlue,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
          ),
          elevation: 2,
          shadowColor: _authBlueDark.withValues(alpha: 0.4),
        ),
        child: const Text('Войти'),
      ),
    );
  }

  Widget _buildAuthTitle() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          'SmartList',
          style: GoogleFonts.inter(
            fontSize: 28,
            fontWeight: FontWeight.w700,
            color: _authBlue,
          ),
        ),
        const SizedBox(width: 8),
        Text(
          'ID',
          style: GoogleFonts.inter(
            fontSize: 28,
            fontWeight: FontWeight.w500,
            color: Colors.white,
          ),
        ),
      ],
    );
  }

  Widget _buildAuthCard({required Widget child}) {
    return Container(
      decoration: BoxDecoration(
        color: _authCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _authBlue, width: 2),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.24),
            blurRadius: 20,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: child,
    );
  }

  Widget _buildAuthLabeledField({required String label, required Widget child}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        Theme(
          data: Theme.of(context).copyWith(
            inputDecorationTheme: InputDecorationTheme(
              filled: true,
              fillColor: Colors.white,
              hintStyle: const TextStyle(color: Colors.black38),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 2),
              ),
            ),
          ),
          child: child,
        ),
      ],
    );
  }
}

class RegisterPage extends StatefulWidget {
  const RegisterPage({super.key});

  @override
  State<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends State<RegisterPage> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _surnameController = TextEditingController();
  final _loginController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscure = true;
  bool _isSaving = false;

  @override
  void dispose() {
    _nameController.dispose();
    _surnameController.dispose();
    _loginController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _register() async {
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
        const SnackBar(content: Text('Аккаунт создан')),
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
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'SmartList',
                          style: GoogleFonts.inter(
                            fontSize: 28,
                            fontWeight: FontWeight.w700,
                            color: _authBlue,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'ID',
                          style: GoogleFonts.inter(
                            fontSize: 28,
                            fontWeight: FontWeight.w500,
                            color: Colors.white,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'Create your account and start planning',
                      style: TextStyle(color: Colors.white60),
                    ),
                    const SizedBox(height: 16),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        'Создать аккаунт',
                        style: GoogleFonts.inter(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    Container(
                      decoration: BoxDecoration(
                        color: _authCard,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: _authBlue, width: 2),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.24),
                            blurRadius: 20,
                            offset: const Offset(0, 8),
                          ),
                        ],
                      ),
                      padding: const EdgeInsets.all(16),
                      child: Form(
                        key: _formKey,
                        child: Column(
                          children: [
                            _buildAuthField(
                              label: 'Имя',
                              controller: _nameController,
                              hint: 'Иван',
                            ),
                            const SizedBox(height: 12),
                            _buildAuthField(
                              label: 'Фамилия',
                              controller: _surnameController,
                              hint: 'Иванов',
                            ),
                            const SizedBox(height: 12),
                            _buildAuthField(
                              label: 'Логин',
                              controller: _loginController,
                              hint: 'IvanIvanov2000',
                            ),
                            const SizedBox(height: 12),
                            _buildAuthField(
                              label: 'Пароль',
                              controller: _passwordController,
                              hint: '*************',
                              obscureText: _obscure,
                              suffix: IconButton(
                                icon: Icon(
                                  _obscure
                                      ? Icons.visibility
                                      : Icons.visibility_off,
                                  color: Colors.white54,
                                ),
                                onPressed: () =>
                                    setState(() => _obscure = !_obscure),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 18),
                    _isSaving
                        ? const SizedBox(
                      height: 26,
                      width: 26,
                      child: CircularProgressIndicator(
                        color: _authBlue,
                        strokeWidth: 2.4,
                      ),
                    )
                        : SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _register,
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          backgroundColor: _authBlue,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(24),
                          ),
                          elevation: 2,
                          shadowColor: _authBlueDark.withValues(alpha: 0.4),
                        ),
                        child: const Text('Зарегистрироваться'),
                      ),
                    ),
                    const SizedBox(height: 8),
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text(
                        'Уже есть аккаунт? Войти',
                        style: TextStyle(color: _authBlue),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAuthField({
    required String label,
    required TextEditingController controller,
    required String hint,
    bool obscureText = false,
    Widget? suffix,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          obscureText: obscureText,
          validator: (value) {
            if (value == null || value.trim().isEmpty) {
              return 'Заполните поле';
            }
            if (label == 'Логин' && value.trim().length < 3) {
              return 'Минимум 3 символа';
            }
            if (label == 'Пароль' && value.trim().length < 8) {
              return 'Минимум 8 символов';
            }
            return null;
          },
          decoration: InputDecoration(
            filled: true,
            fillColor: Colors.white,
            hintText: hint,
            hintStyle: const TextStyle(color: Colors.black38),
            prefixIcon: label == 'Имя'
                ? const Icon(Icons.person_outline, color: _authBlue)
                : label == 'Фамилия'
                ? const Icon(Icons.badge_outlined, color: _authBlue)
                : label == 'Логин'
                ? const Icon(Icons.person_outline, color: _authBlue)
                : const Icon(Icons.lock_outline, color: _authBlue),
            suffixIcon: suffix,
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: _authBlue, width: 1.5),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: _authBlue, width: 1.5),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(16),
              borderSide: const BorderSide(color: _authBlue, width: 2),
            ),
          ),
        ),
      ],
    );
  }
}

class HomeShell extends StatefulWidget {
  final String login;
  final String password;

  const HomeShell({
    super.key,
    this.login = 'Пользователь',
    this.password = '',
  });

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _currentIndex = 0;
  final _listsKey = GlobalKey<_ListsPageState>();
  final _homeKey = GlobalKey<_HomeTabState>();
  final _searchKey = GlobalKey<_SearchTabState>();


  @override
  Widget build(BuildContext context) {
    final pages = [
      _HomeTab(
        key: _homeKey,
        login: widget.login,
        onNavigate: _setTab,
        onSearchForList: openSearchForList,
        onQuickAdd: (name) async {
          _setTab(1);
          await _searchKey.currentState?.quickAdd(name);
        },
      ),
      _SearchTab(
        key: _searchKey,
      ),
      ListsPage(
        key: _listsKey,
        login: widget.login,
        password: widget.password,
        onSearchForList: openSearchForList,
      ),
      _ProfileTab(
        login: widget.login,
        onOpenListsTab: () => _setTab(2),
      ),
    ];

    return Scaffold(
      backgroundColor: _authBg,
      body: IndexedStack(
        index: _currentIndex,
        children: pages,
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _authBlue, width: 2),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 12,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 14),
        child: BottomNavigationBar(
          currentIndex: _currentIndex,
          onTap: (index) {
            _setTab(index);
          },
          type: BottomNavigationBarType.fixed,
          backgroundColor: Colors.transparent,
          selectedItemColor: _authBlue,
          unselectedItemColor: const Color(0xFF8E98A5),
          showSelectedLabels: false,
          showUnselectedLabels: false,
          items: const [
            BottomNavigationBarItem(
              icon: Icon(Icons.home_outlined),
              label: '',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.search),
              label: '',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.format_list_bulleted),
              label: '',
            ),
            BottomNavigationBarItem(
              icon: Icon(Icons.person_outline),
              label: '',
            ),
          ],
        ),
      ),
    );
  }

  void _setTab(int index) {
    setState(() => _currentIndex = index);
    if (index == 0) {
      _homeKey.currentState?.refresh();
    }
    if (index == 1) {
      _searchKey.currentState?.requestFocus();
    }
    if (index == 2) {
      _listsKey.currentState?.refresh();
    }
  }

  /// Открыть вкладку поиска с прицелом на конкретный список:
  /// добавление идет сразу в него без диалога выбора.
  void openSearchForList(String listId, String listName) {
    _searchKey.currentState?.setTargetList(listId, listName);
    _setTab(1);
  }
}

class _ShoppingList {
  final String id;
  final String name;
  final bool isFavorite;
  final bool isDeleted;
  final DateTime? deletedAt;
  final DateTime createdAt;
  final List<_ShoppingItem> items;
  final bool isShared;
  final bool isOwner;
  final bool isSystem;
  final String role;
  final int itemCount;
  final int checkedCount;

  _ShoppingList({
    required this.name,
    String? id,
    this.isSystem = false,
  })  : id = id ?? DateTime.now().microsecondsSinceEpoch.toString(),
        isFavorite = isSystem,
        isDeleted = false,
        deletedAt = null,
        createdAt = DateTime.now(),
        items = const <_ShoppingItem>[],
        isShared = false,
        isOwner = true,
        role = 'owner',
        itemCount = 0,
        checkedCount = 0;

  _ShoppingList._({
    required this.id,
    required this.name,
    required this.isFavorite,
    required this.isDeleted,
    required this.deletedAt,
    required this.createdAt,
    required this.items,
    this.isShared = false,
    this.isOwner = true,
    this.isSystem = false,
    this.role = 'owner',
    this.itemCount = 0,
    this.checkedCount = 0,
  });

  factory _ShoppingList.fromApi(ApiShoppingList apiList, [List<_ShoppingItem>? items]) {
    return _ShoppingList._(
      id: apiList.id,
      name: apiList.name,
      isFavorite: apiList.isSystem,
      isDeleted: false,
      deletedAt: null,
      createdAt: apiList.createdAt,
      items: items ?? <_ShoppingItem>[],
      isShared: apiList.isShared,
      isOwner: apiList.isOwner,
      isSystem: apiList.isSystem,
      role: apiList.role,
      itemCount: apiList.itemCount,
      checkedCount: apiList.checkedCount,
    );
  }

  _ShoppingList copyWith({
    String? name,
    bool? isFavorite,
    bool? isDeleted,
    DateTime? deletedAt,
    bool clearDeletedAt = false,
    List<_ShoppingItem>? items,
    bool? isShared,
    bool? isOwner,
    bool? isSystem,
    String? role,
    int? itemCount,
    int? checkedCount,
  }) {
    return _ShoppingList._(
      id: id,
      name: name ?? this.name,
      isFavorite: isFavorite ?? this.isFavorite,
      isDeleted: isDeleted ?? this.isDeleted,
      deletedAt: clearDeletedAt ? null : deletedAt ?? this.deletedAt,
      createdAt: createdAt,
      items: items ?? this.items,
      isShared: isShared ?? this.isShared,
      isOwner: isOwner ?? this.isOwner,
      isSystem: isSystem ?? this.isSystem,
      role: role ?? this.role,
      itemCount: itemCount ?? this.itemCount,
      checkedCount: checkedCount ?? this.checkedCount,
    );
  }
}

class _HomeRecommendationItem {
  final String name;
  final String badgeText;
  final Color badgeColor;
  final IconData icon;
  final String? detail;

  _HomeRecommendationItem({
    required this.name,
    required this.badgeText,
    required this.badgeColor,
    this.icon = Icons.shopping_bag_outlined,
    this.detail,
  });
}

class _HomeTab extends StatefulWidget {
  final String login;
  final void Function(int index) onNavigate;
  final void Function(String listId, String listName) onSearchForList;
  final Future<void> Function(String name) onQuickAdd;

  const _HomeTab({
    super.key,
    required this.login,
    required this.onNavigate,
    required this.onSearchForList,
    required this.onQuickAdd,
  });

  @override
  State<_HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<_HomeTab> {
  final List<_ShoppingList> _lists = [];
  final List<_HomeRecommendationItem> _recommendations = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> refresh() => _loadData();

  Future<void> _loadData() async {
    if (!mounted) return;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final apiLists = await ApiService.instance.getLists();
      if (!mounted) return;

      final recs = <_HomeRecommendationItem>[];
      final seen = <String>{};

      // 1. Рекомендации по совстречаемости из базы данных
      if (apiLists.isNotEmpty) {
        String? targetListId;
        for (final l in apiLists) {
          if (l.itemCount > 0) {
            targetListId = l.id;
            break;
          }
        }
        if (targetListId != null) {
          try {
            final suggestions = await ApiService.instance.getListSuggestions(targetListId, limit: 6);
            for (final s in suggestions) {
              final key = s.name.trim().toLowerCase();
              if (key.isNotEmpty && seen.add(key)) {
                recs.add(_HomeRecommendationItem(
                  name: s.name,
                  badgeText: 'Часто берут',
                  badgeColor: _authBlue,
                  icon: Icons.auto_awesome_rounded,
                  detail: 'К товарам в списке',
                ));
              }
              if (recs.length >= 6) break;
            }
          } catch (_) {}
        }
      }

      // 2. Базовые товары каталога (если аккаунт новый или история пуста)
      if (recs.length < 6) {
        try {
          final products = await ApiService.instance.getProducts(limit: 6);
          for (final p in products) {
            final key = p.name.trim().toLowerCase();
            if (key.isNotEmpty && seen.add(key)) {
              recs.add(_HomeRecommendationItem(
                name: p.name,
                badgeText: 'Популярное',
                badgeColor: const Color(0xFF10B981),
                icon: Icons.local_fire_department_rounded,
                detail: p.categoryName ?? (p.defaultUnit != null && p.defaultUnit!.isNotEmpty ? 'в ${p.defaultUnit}' : null),
              ));
            }
            if (recs.length >= 6) break;
          }
        } catch (_) {}
      }

      setState(() {
        _lists
          ..clear()
          ..addAll(apiLists.map((l) => _ShoppingList.fromApi(l)));
        _recommendations
          ..clear()
          ..addAll(recs);
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _openList(_ShoppingList list) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ListDetailsPage(
          listId: list.id,
          listTitle: list.name,
          onSearchForList: widget.onSearchForList,
        ),
      ),
    );
    if (mounted) {
      await _loadData();
    }
  }

  Future<void> _createListDialog() async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          title: const Text('Новый список товаров', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          content: TextField(
            controller: controller,
            autofocus: true,
            style: const TextStyle(color: Colors.white),
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              hintText: 'Название (например, Продукты)',
              hintStyle: const TextStyle(color: Colors.white54),
              filled: true,
              fillColor: Colors.black.withValues(alpha: 0.25),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 2),
              ),
            ),
            onSubmitted: (v) => Navigator.pop(context, v),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Отмена', style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, controller.text),
              style: ElevatedButton.styleFrom(
                backgroundColor: _authBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              child: const Text('Создать'),
            ),
          ],
        );
      },
    );

    final name = (result ?? '').trim();
    if (name.isEmpty) return;

    try {
      final created = await ApiService.instance.createList(name);
      if (!mounted) return;
      await _loadData();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Список "$name" успешно создан в базе данных')),
      );
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ListDetailsPage(
            listId: created.id,
            listTitle: created.name,
            onSearchForList: widget.onSearchForList,
          ),
        ),
      );
      if (mounted) {
        await _loadData();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка создания списка: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          SafeArea(
            child: RefreshIndicator(
              color: _authBlue,
              backgroundColor: _authCard,
              onRefresh: _loadData,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                children: [
                  _HomeSearchBar(
                    onTap: () => widget.onNavigate(1),
                  ),
                  const SizedBox(height: 18),
                  _buildListsSectionHeader(),
                  const SizedBox(height: 12),
                  if (_isLoading && _lists.isEmpty)
                    _buildLoadingIndicator()
                  else if (_errorMessage != null && _lists.isEmpty)
                    _buildErrorWidget()
                  else if (_lists.isEmpty)
                    _buildEmptyListsCard()
                  else
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        ..._lists.take(3).map(_buildShoppingListCard),
                    if (_lists.length > 3)
                      Padding(
                        padding: const EdgeInsets.only(top: 2, bottom: 4),
                        child: SizedBox(
                          width: double.infinity,
                          child: OutlinedButton.icon(
                            onPressed: () => widget.onNavigate(2),
                            icon: const Icon(Icons.format_list_bulleted, size: 18),
                            label: Text('Все списки (${_lists.length})'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: _authBlue,
                              side: BorderSide(color: _authBlue.withValues(alpha: 0.6)),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                          ),
                        ),
                        ),
                      ],
                    ),
                  if (_recommendations.isNotEmpty) ...[
                    const SizedBox(height: 20),
                    _buildRecommendationsHeader(),
                    const SizedBox(height: 12),
                    _buildRecommendationsGrid(),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildListsSectionHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Text(
              'Списки товаров',
              style: GoogleFonts.inter(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
            ),
            if (!_isLoading && _lists.isNotEmpty) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: _authBlue.withValues(alpha: 0.25),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: _authBlue.withValues(alpha: 0.6)),
                ),
                child: Text(
                  '${_lists.length}',
                  style: const TextStyle(
                    color: _authBlue,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ],
        ),
        TextButton.icon(
          onPressed: _createListDialog,
          icon: const Icon(Icons.add_circle_outline, size: 18),
          label: const Text('Новый список'),
          style: TextButton.styleFrom(
            foregroundColor: _authBlue,
            textStyle: const TextStyle(fontWeight: FontWeight.w700),
          ),
        ),
      ],
    );
  }

  Widget _buildLoadingIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 36),
      alignment: Alignment.center,
      child: const Column(
        children: [
          CircularProgressIndicator(color: _authBlue),
          SizedBox(height: 12),
          Text(
            'Загрузка списков из базы данных...',
            style: TextStyle(color: Colors.white60, fontSize: 13),
          ),
        ],
      ),
    );
  }

  Widget _buildErrorWidget() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _authCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _danger.withValues(alpha: 0.5)),
      ),
      child: Column(
        children: [
          const Icon(Icons.cloud_off_outlined, color: _danger, size: 36),
          const SizedBox(height: 8),
          const Text(
            'Не удалось загрузить данные из базы',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            _errorMessage ?? '',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white60, fontSize: 12),
          ),
          const SizedBox(height: 12),
          ElevatedButton.icon(
            onPressed: _loadData,
            icon: const Icon(Icons.refresh, size: 16),
            label: const Text('Повторить'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _authBlue,
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyListsCard() {
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: _authCard,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _authBlue.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: _authBlue.withValues(alpha: 0.12),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.format_list_bulleted_add, color: _authBlue, size: 36),
          ),
          const SizedBox(height: 12),
          Text(
            'У вас пока нет списков товаров',
            style: GoogleFonts.inter(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Создайте свой первый список, и он сохранится в базе данных',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white60, fontSize: 13),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: _createListDialog,
            icon: const Icon(Icons.add, size: 18),
            label: const Text('Создать список'),
            style: ElevatedButton.styleFrom(
              backgroundColor: _authBlue,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildShoppingListCard(_ShoppingList list) {
    final hasItems = list.itemCount > 0;
    final progress = hasItems ? (list.checkedCount / list.itemCount).clamp(0.0, 1.0) : 0.0;
    final isDone = hasItems && list.checkedCount >= list.itemCount;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => _openList(list),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: isDone ? const Color(0xFF10B981) : _authBlue,
              width: 1.8,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.08),
                blurRadius: 10,
                offset: const Offset(0, 3),
              ),
            ],
          ),
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: isDone
                          ? const Color(0xFFE6F9F0)
                          : _authBlue.withValues(alpha: 0.12),
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      isDone
                          ? Icons.check_circle_outline
                          : (list.isSystem ? Icons.star_rounded : Icons.shopping_bag_outlined),
                      color: isDone ? const Color(0xFF10B981) : _authBlue,
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          list.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: GoogleFonts.inter(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: _ink,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          hasItems
                              ? '${list.checkedCount} из ${list.itemCount} куплено'
                              : 'Список пока пуст',
                          style: TextStyle(
                            fontSize: 12,
                            color: hasItems ? _muted : Colors.black45,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (list.isShared) ...[
                    Container(
                      margin: const EdgeInsets.only(right: 6),
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                      decoration: BoxDecoration(
                        color: const Color(0xFF8B5CF6).withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.people_outline, size: 12, color: Color(0xFF8B5CF6)),
                          SizedBox(width: 3),
                          Text(
                            'Общий',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              color: Color(0xFF8B5CF6),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const Icon(
                    Icons.arrow_forward_ios_rounded,
                    size: 15,
                    color: Colors.black38,
                  ),
                ],
              ),
              if (hasItems) ...[
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: progress,
                    minHeight: 5,
                    backgroundColor: const Color(0xFFE5E7EB),
                    valueColor: AlwaysStoppedAnimation<Color>(
                      isDone ? const Color(0xFF10B981) : _authBlue,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildRecommendationsHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            const Icon(Icons.auto_awesome, color: _authBlue, size: 18),
            const SizedBox(width: 6),
            Text(
              'Рекомендуем купить',
              style: GoogleFonts.inter(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
            ),
          ],
        ),
        TextButton(
          onPressed: () => widget.onNavigate(1),
          style: TextButton.styleFrom(foregroundColor: _authBlue),
          child: const Text('Каталог'),
        ),
      ],
    );
  }

  Widget _buildRecommendationsGrid() {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _recommendations.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 1.55,
      ),
      itemBuilder: (context, index) {
        final item = _recommendations[index];
        return _HomeRecommendationCard(
          item: item,
          onAdd: () => _addRecommendationWithPicker(capName(item.name)),
        );
      },
    );
  }

  Future<void> _addRecommendationWithPicker(String name) async {
    try {
      final parsed = await ApiService.instance.parseItem(name);
      if (!mounted) return;

      if (_lists.isEmpty) {
        final newName = await _promptNewListName();
        if (newName == null || newName.trim().isEmpty) return;
        await ApiService.instance.createList(newName.trim(), items: [parsed.name]);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Товар "${parsed.name}" добавлен в новый список "$newName"')),
          );
          await _loadData();
        }
        return;
      }

      final picked = await _pickTargetListId(lists: _lists);
      if (picked == null || !mounted) return;

      if (picked == '__create__') {
        final newName = await _promptNewListName();
        if (newName == null || newName.trim().isEmpty) return;
        await ApiService.instance.createList(newName.trim(), items: [parsed.name]);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Товар "${parsed.name}" добавлен в новый список "$newName"')),
          );
          await _loadData();
        }
        return;
      }

      await ApiService.instance.addItem(
        picked,
        parsed.name,
        quantity: parsed.quantity,
        unit: parsed.unit,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Товар "${parsed.name}" добавлен в список')),
        );
        await _loadData();
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<String?> _promptNewListName() async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          title: const Text('Новый список', style: TextStyle(color: Colors.white)),
          content: TextField(
            controller: controller,
            autofocus: true,
            style: const TextStyle(color: Colors.white),
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              hintText: 'Название списка',
              hintStyle: const TextStyle(color: Colors.white54),
              filled: true,
              fillColor: Colors.black.withValues(alpha: 0.15),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
            ),
            onSubmitted: (v) => Navigator.pop(context, v),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Отмена', style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, controller.text),
              style: ElevatedButton.styleFrom(
                backgroundColor: _authBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text('Создать'),
            ),
          ],
        );
      },
    );
    final name = (result ?? '').trim();
    return name.isEmpty ? null : name;
  }

  Future<String?> _pickTargetListId({
    required List<_ShoppingList> lists,
  }) async {
    if (!mounted) return null;

    return showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return Container(
          decoration: BoxDecoration(
            color: _authCard,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(22)),
            border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
          ),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          child: SafeArea(
            top: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 46,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.white24,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Куда добавить товар?',
                        style: GoogleFonts.inter(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    TextButton.icon(
                      onPressed: () => Navigator.pop(context, '__create__'),
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('Новый'),
                      style: TextButton.styleFrom(foregroundColor: _authBlue),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 320),
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: lists.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final list = lists[index];
                      return InkWell(
                        borderRadius: BorderRadius.circular(16),
                        onTap: () => Navigator.pop(context, list.id),
                        child: Container(
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: _authBlue, width: 1.8),
                          ),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  list.name,
                                  style: const TextStyle(
                                    color: _ink,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                              if (list.isFavorite)
                                const Icon(Icons.favorite, color: _authBlue, size: 18),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
                if (lists.isEmpty) ...[
                  const SizedBox(height: 10),
                  const Text(
                    'Списков пока нет. Создайте новый, чтобы добавить товар.',
                    style: TextStyle(color: Colors.white60),
                    textAlign: TextAlign.center,
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _HomeSearchBar extends StatelessWidget {
  final VoidCallback onTap;

  const _HomeSearchBar({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        borderRadius: BorderRadius.circular(22),
        onTap: onTap,
        child: Container(
          height: 44,
          padding: const EdgeInsets.symmetric(horizontal: 14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: _authBlue, width: 1.6),
          ),
          child: const Row(
            children: [
              Icon(Icons.search, color: Colors.black),
              Expanded(
                child: Center(
                  child: Text(
                    'Поиск',
                    style: TextStyle(color: Colors.black45),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HomeRecommendationCard extends StatelessWidget {
  final _HomeRecommendationItem item;
  final VoidCallback onAdd;

  const _HomeRecommendationCard({
    required this.item,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _authBlue.withValues(alpha: 0.35), width: 1.4),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: item.badgeColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(item.icon, size: 11, color: item.badgeColor),
                    const SizedBox(width: 3),
                    Text(
                      item.badgeText,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: item.badgeColor,
                      ),
                    ),
                  ],
                ),
              ),
              InkResponse(
                onTap: onAdd,
                radius: 16,
                child: Container(
                  padding: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: _authBlue,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.add, color: Colors.white, size: 14),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            capName(item.name),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: _ink,
            ),
          ),
          if (item.detail != null && item.detail!.isNotEmpty)
            Text(
              item.detail!,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 10,
                color: _muted,
                fontWeight: FontWeight.w500,
              ),
            )
          else
            const SizedBox(height: 12),
        ],
      ),
    );
  }
}
class _SearchTab extends StatefulWidget {

  const _SearchTab({
    super.key,
  });

  @override
  State<_SearchTab> createState() => _SearchTabState();
}

class _SearchTabState extends State<_SearchTab> {
  final TextEditingController _controller = TextEditingController();
  final FocusNode _focusNode = FocusNode();


  final List<ApiCategory> _categories = [];
  final List<ApiCatalogProduct> _catalogProducts = [];
  final List<String> _searchHistory = [];
  final List<ApiCatalogProduct> _searchResults = [];
  final List<ApiItemSuggestion> _searchSuggestions = [];
  String? _selectedCategoryId;
  bool _loadingCatalog = false;
  bool _searching = false;
  int _visibleCount = 10;
  Timer? _debounce;
  String _activeQuery = '';
  String? _targetListId;
  String? _targetListName;

  @override
  void initState() {
    super.initState();
    _loadHistory();
    _loadCategoriesAndProducts();
  }

  Future<void> _loadHistory() async {
    try {
      final history = await ApiService.instance.getSearchHistory();
      if (!mounted) return;
      setState(() {
        _searchHistory
          ..clear()
          ..addAll(history);
      });
    } catch (_) {}
  }

  Future<void> _loadCategoriesAndProducts() async {
    setState(() {
      _loadingCatalog = true;
      _visibleCount = 10;
    });
    try {
      final results = await Future.wait([
        ApiService.instance.getCategories(),
        ApiService.instance.getProducts(limit: 200),
      ]);
      if (!mounted) return;
      setState(() {
        _categories
          ..clear()
          ..addAll(results[0] as List<ApiCategory>);
        _catalogProducts
          ..clear()
          ..addAll(results[1] as List<ApiCatalogProduct>);
        _loadingCatalog = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loadingCatalog = false);
    }
  }

  /// Вызывается из открытого списка: поиск будет добавлять товары
  /// сразу в этот список без диалога выбора.
  void setTargetList(String listId, String listName) {
    if (!mounted) return;
    setState(() {
      _targetListId = listId;
      _targetListName = listName;
      _controller.clear();
    });
    _focusNode.requestFocus();
  }

  void clearTargetList() {
    if (!mounted) return;
    setState(() {
      _targetListId = null;
      _targetListName = null;
    });
  }

  void _onQueryChanged(String value) {
    _debounce?.cancel();
    final q = value.trim();
    if (q.isEmpty) {
      if (!mounted) return;
      setState(() {
        _activeQuery = '';
        _searchResults.clear();
        _searchSuggestions.clear();
        _searching = false;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 400), () => _runSearch(q));
  }

  Future<void> _runSearch(String query) async {
    final q = query.trim();
    if (q.isEmpty || !mounted) return;
    setState(() {
      _activeQuery = q;
      _searching = true;
      _searchSuggestions.clear();
    });
    try {
      final products = await ApiService.instance.searchCatalog(q);
      if (!mounted) return;
      // Ответ мог прийти уже для другого запроса — показываем только свежий.
      if (_controller.text.trim() != q && _activeQuery != q) return;
      setState(() {
        _searchResults
          ..clear()
          ..addAll(products);
        _searching = false;
      });
      _loadSuggestionsFor(q, products);
    } catch (_) {
      if (mounted) {
        setState(() {
          _searchResults.clear();
          _searchSuggestions.clear();
          _searching = false;
        });
      }
    }
  }

  /// Подсказки «часто берут вместе» к текущему запросу и найденным товарам.
  Future<void> _loadSuggestionsFor(
    String query,
    List<ApiCatalogProduct> products,
  ) async {
    final seeds = <String>[];
    void addSeed(String value) {
      final trimmed = value.trim();
      if (trimmed.isEmpty) return;
      final key = trimmed.toLowerCase();
      if (seeds.any((seed) => seed.toLowerCase() == key)) return;
      seeds.add(trimmed);
    }

    // Сам запрос может быть товаром, а первый результат — самым релевантным.
    addSeed(query);
    if (products.isNotEmpty) addSeed(products.first.name);
    if (seeds.isEmpty) return;

    final fetched = await ApiService.instance.getItemsSuggestions(
      seeds,
      limit: 6,
    );
    if (!mounted || _activeQuery != query) return;

    final seen = products.map((p) => p.name.trim().toLowerCase()).toSet();
    final filtered = <ApiItemSuggestion>[];
    for (final suggestion in fetched) {
      final key = suggestion.name.trim().toLowerCase();
      if (key.isEmpty || !seen.add(key)) continue;
      filtered.add(suggestion);
    }

    setState(() {
      _searchSuggestions
        ..clear()
        ..addAll(filtered.take(6));
    });
  }

  Widget _buildSearchSuggestions() {
    if (_searchSuggestions.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: _authCard,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, color: _authBlue, size: 16),
              const SizedBox(width: 6),
              Text(
                'С этим часто берут:',
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.white70,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: _searchSuggestions.map((suggestion) {
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ActionChip(
                    avatar: const Icon(Icons.add, size: 15, color: _authBlue),
                    label: Text(
                      capName(suggestion.name),
                      style: const TextStyle(color: Colors.white, fontSize: 13),
                    ),
                    backgroundColor: Colors.black.withValues(alpha: 0.25),
                    side: BorderSide(color: _authBlue.withValues(alpha: 0.45)),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    onPressed: () => _addWithPicker(capName(suggestion.name)),
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _selectCategory(String? categoryId) async {
    setState(() {
      _selectedCategoryId = categoryId;
      _loadingCatalog = true;
      _visibleCount = 10;
    });
    try {
      final products = await ApiService.instance.getProducts(
        categoryId: categoryId,
        limit: 200,
      );
      if (!mounted) return;
      setState(() {
        _catalogProducts
          ..clear()
          ..addAll(products);
        _loadingCatalog = false;
      });
    } catch (_) {
      if (mounted) setState(() => _loadingCatalog = false);
    }
  }

  Future<String?> _createListDialog(BuildContext context) async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          title: const Text('Новый список', style: TextStyle(color: Colors.white)),
          content: TextField(
            controller: controller,
            autofocus: true,
            style: const TextStyle(color: Colors.white),
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              hintText: 'Название списка',
              hintStyle: const TextStyle(color: Colors.white54),
              filled: true,
              fillColor: Colors.black.withValues(alpha: 0.15),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
            ),
            onSubmitted: (v) => Navigator.pop(context, v),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Отмена', style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, controller.text),
              style: ElevatedButton.styleFrom(
                backgroundColor: _authBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text('Создать'),
            ),
          ],
        );
      },
    );
    final name = (result ?? '').trim();
    return name.isEmpty ? null : name;
  }

  Future<String?> _pickTargetListId({
    required List<_ShoppingList> lists,
  }) async {
    if (!mounted) return null;

    return showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return Container(
          decoration: BoxDecoration(
            color: _authCard,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(22)),
            border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
          ),
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          child: SafeArea(
            top: false,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 46,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.white24,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Куда добавить товар?',
                        style: GoogleFonts.inter(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    TextButton.icon(
                      onPressed: () => Navigator.pop(context, '__create__'),
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('Новый'),
                      style: TextButton.styleFrom(foregroundColor: _authBlue),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxHeight: 320),
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: lists.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final list = lists[index];
                      return InkWell(
                        borderRadius: BorderRadius.circular(16),
                        onTap: () => Navigator.pop(context, list.id),
                        child: Container(
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(16),
                            border: Border.all(color: _authBlue, width: 1.8),
                          ),
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  list.name,
                                  style: const TextStyle(
                                    color: _ink,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                              ),
                              if (list.isFavorite)
                                const Icon(Icons.favorite, color: _authBlue, size: 18),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
                if (lists.isEmpty) ...[
                  const SizedBox(height: 10),
                  const Text(
                    'Списков пока нет. Создайте новый, чтобы добавить товар.',
                    style: TextStyle(color: Colors.white60),
                    textAlign: TextAlign.center,
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _addWithPicker(String name) async {
    try {
      final trimmed = name.trim();
      if (trimmed.isNotEmpty) {
        await ApiService.instance.addSearchQuery(trimmed);
        _loadHistory();
      }
      final parsed = await ApiService.instance.parseItem(name);
      final targetId = _targetListId;
      final targetName = _targetListName;
      if (targetId != null) {
        await ApiService.instance.addItem(
          targetId,
          parsed.name,
          quantity: parsed.quantity,
          unit: parsed.unit,
        );
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Товар "${parsed.name}" добавлен в список "${targetName ?? ''}"')),
          );
        }
        return;
      }
      final apiLists = await ApiService.instance.getLists();
      final lists = apiLists.map((l) => _ShoppingList.fromApi(l)).toList();
      if (!mounted) return;

      if (lists.isEmpty) {
        final newName = await _createListDialog(context);
        if (newName == null || newName.trim().isEmpty) return;
        await ApiService.instance.createList(newName.trim(), items: [parsed.name]);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Товар "${parsed.name}" добавлен в новый список "$newName"')),
          );
        }
        return;
      }

      final picked = await _pickTargetListId(lists: lists);
      if (picked == null || !mounted) return;

      if (picked == '__create__') {
        final newName = await _createListDialog(context);
        if (newName == null || newName.trim().isEmpty) return;
        await ApiService.instance.createList(newName.trim(), items: [parsed.name]);
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Товар "${parsed.name}" добавлен в новый список "$newName"')),
          );
        }
        return;
      }

      await ApiService.instance.addItem(
        picked,
        parsed.name,
        quantity: parsed.quantity,
        unit: parsed.unit,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Товар "${parsed.name}" добавлен в список')),
        );
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }



  Future<void> quickAdd(String name) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) return;
    await _addWithPicker(trimmed);
  }

  void requestFocus() {
    if (!_focusNode.hasFocus) {
      _focusNode.requestFocus();
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
              children: [
                Text(
                  'Поиск товаров',
                  style: GoogleFonts.inter(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 6),
                const Text(
                  'Ищет по русским и английским названиям.',
                  style: TextStyle(color: Colors.white60),
                ),
                const SizedBox(height: 12),
                if (_targetListId != null) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    decoration: BoxDecoration(
                      color: _authBlue.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: _authBlue.withValues(alpha: 0.6)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.playlist_add, color: _authBlue, size: 18),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Добавление в список «${_targetListName ?? ''}»',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                        ),
                        InkWell(
                          onTap: clearTargetList,
                          borderRadius: BorderRadius.circular(999),
                          child: const Padding(
                            padding: EdgeInsets.all(4),
                            child: Icon(Icons.close, color: Colors.white60, size: 16),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                ],
                TextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  textInputAction: TextInputAction.search,
                  keyboardType: TextInputType.text,
                  textCapitalization: TextCapitalization.sentences,
                  onChanged: _onQueryChanged,
                  onSubmitted: (v) {
                    if (v.trim().isNotEmpty) {
                      _debounce?.cancel();
                      _runSearch(v.trim());
                    }
                  },
                  decoration: InputDecoration(
                    hintText: 'Поиск по каталогу (молоко, сыр...)',
                    prefixIcon: const Icon(Icons.search, color: _authBlue),
                    suffixIcon: ValueListenableBuilder<TextEditingValue>(
                      valueListenable: _controller,
                      builder: (context, value, _) {
                        if (value.text.isEmpty) return const SizedBox.shrink();
                        return IconButton(
                          icon: const Icon(Icons.clear, color: Colors.black38),
                          onPressed: () {
                            _controller.clear();
                            _onQueryChanged('');
                          },
                        );
                      },
                    ),
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
                ),
                if (_activeQuery.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      const Icon(Icons.manage_search, color: _authBlue, size: 18),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Найдено: ${_searching ? '…' : _searchResults.length}',
                          style: GoogleFonts.inter(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  if (_searching)
                    const Center(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: CircularProgressIndicator(color: _authBlue),
                      ),
                    )
                  else if (_searchResults.isEmpty)
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: _authCard,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
                      ),
                      child: Column(
                        children: [
                          const Text(
                            'Ничего не найдено',
                            style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 8),
                          SizedBox(
                            width: double.infinity,
                            child: OutlinedButton.icon(
                              onPressed: () => _addWithPicker(_activeQuery),
                              icon: const Icon(Icons.add, size: 18),
                              label: Text('Добавить «$_activeQuery» как свой товар'),
                              style: OutlinedButton.styleFrom(
                                foregroundColor: _authBlue,
                                side: BorderSide(color: _authBlue.withValues(alpha: 0.6)),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(14),
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    Container(
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: _authBlue.withValues(alpha: 0.4), width: 1.2),
                      ),
                      child: ListView.separated(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        padding: const EdgeInsets.all(8),
                        itemCount: _searchResults.length,
                        separatorBuilder: (_, _) => const Divider(height: 1, color: _border),
                        itemBuilder: (context, index) {
                          final item = _searchResults[index];
                          final sub = item.defaultUnit != null && item.defaultUnit!.isNotEmpty
                              ? item.defaultUnit!
                              : (item.categoryName ?? '');
                          return InkWell(
                            borderRadius: BorderRadius.circular(10),
                            onTap: () => _addWithPicker(capName(item.name)),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          capName(item.name),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                          style: const TextStyle(
                                            color: _ink,
                                            fontWeight: FontWeight.w600,
                                            fontSize: 14,
                                          ),
                                        ),
                                        if (sub.isNotEmpty)
                                          Text(
                                            sub,
                                            maxLines: 1,
                                            overflow: TextOverflow.ellipsis,
                                            style: const TextStyle(color: _muted, fontSize: 12),
                                          ),
                                      ],
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.all(4),
                                    decoration: BoxDecoration(
                                      color: _authBlue,
                                      borderRadius: BorderRadius.circular(8),
                                    ),
                                    child: const Icon(Icons.add, color: Colors.white, size: 16),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                ],
                if (_searchSuggestions.isNotEmpty) _buildSearchSuggestions(),
                if (_searchHistory.isNotEmpty) ...[
                  const SizedBox(height: 18),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.history_rounded, color: _authBlue, size: 18),
                          const SizedBox(width: 6),
                          Text(
                            'История поиска',
                            style: GoogleFonts.inter(
                              fontSize: 15,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                      TextButton(
                        onPressed: () async {
                          await ApiService.instance.clearSearchHistory();
                          _loadHistory();
                        },
                        style: TextButton.styleFrom(
                          foregroundColor: Colors.white60,
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          minimumSize: Size.zero,
                          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        ),
                        child: const Text('Очистить', style: TextStyle(fontSize: 12)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: _searchHistory.map((query) {
                      return InkWell(
                        borderRadius: BorderRadius.circular(20),
                        onTap: () {
                          _controller.text = query;
                          _focusNode.requestFocus();
                          _debounce?.cancel();
                          _runSearch(query);
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: _authCard,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.search, size: 13, color: _authBlue),
                              const SizedBox(width: 5),
                              Text(
                                capName(query),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 12,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                              const SizedBox(width: 5),
                              GestureDetector(
                                onTap: () async {
                                  await ApiService.instance.removeSearchQuery(query);
                                  _loadHistory();
                                },
                                child: const Icon(Icons.close, size: 13, color: Colors.white38),
                              ),
                            ],
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ],
                const SizedBox(height: 20),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Категории каталога',
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                    if (_categories.isNotEmpty)
                      Text(
                        '${_categories.length} категорий',
                        style: const TextStyle(color: Colors.white54, fontSize: 12),
                      ),
                  ],
                ),
                const SizedBox(height: 10),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          selected: _selectedCategoryId == null,
                          label: const Text('Все товары'),
                          labelStyle: TextStyle(
                            color: _selectedCategoryId == null ? Colors.white : Colors.white70,
                            fontWeight: FontWeight.w600,
                            fontSize: 12,
                          ),
                          backgroundColor: _authCard,
                          selectedColor: _authBlue,
                          side: BorderSide(
                            color: _selectedCategoryId == null ? _authBlue : Colors.white24,
                          ),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          onSelected: (_) => _selectCategory(null),
                        ),
                      ),
                      ..._categories.map((cat) {
                        final isSelected = _selectedCategoryId == cat.id;
                        return Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: FilterChip(
                            selected: isSelected,
                            label: Text('${cat.name} (${cat.productCount})'),
                            labelStyle: TextStyle(
                              color: isSelected ? Colors.white : Colors.white70,
                              fontWeight: FontWeight.w600,
                              fontSize: 12,
                            ),
                            backgroundColor: _authCard,
                            selectedColor: _authBlue,
                            side: BorderSide(
                              color: isSelected ? _authBlue : Colors.white24,
                            ),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            onSelected: (_) => _selectCategory(cat.id),
                          ),
                        );
                      }),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                if (_loadingCatalog)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: CircularProgressIndicator(color: _authBlue),
                    ),
                  )
                else if (_catalogProducts.isEmpty)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: Text(
                        'В этой категории пока нет товаров',
                        style: TextStyle(color: Colors.white54),
                      ),
                    ),
                  )
                else
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _catalogProducts.length > _visibleCount
                        ? _visibleCount
                        : _catalogProducts.length,
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: 8,
                      crossAxisSpacing: 8,
                      childAspectRatio: 2.1,
                    ),
                    itemBuilder: (context, i) {
                      final item = _catalogProducts[i];
                      final title = capName(item.name);
                      return Container(
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: _authBlue.withValues(alpha: 0.4), width: 1.2),
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    title,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      color: _ink,
                                      fontWeight: FontWeight.w700,
                                      fontSize: 12,
                                    ),
                                  ),
                                  if (item.categoryName != null || item.defaultUnit != null)
                                    Text(
                                      item.defaultUnit != null && item.defaultUnit!.isNotEmpty
                                          ? item.defaultUnit!
                                          : (item.categoryName ?? ''),
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(color: _muted, fontSize: 10),
                                    ),
                                ],
                              ),
                            ),
                            InkResponse(
                              onTap: () => _addWithPicker(title),
                              radius: 16,
                              child: Container(
                                padding: const EdgeInsets.all(4),
                                decoration: BoxDecoration(
                                  color: _authBlue,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Icon(Icons.add, color: Colors.white, size: 14),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                  if (_catalogProducts.length > _visibleCount)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () => setState(() => _visibleCount += 10),
                          icon: const Icon(Icons.expand_more, size: 18),
                          label: Text('Показать еще (осталось ${_catalogProducts.length - _visibleCount})'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: _authBlue,
                            side: BorderSide(color: _authBlue.withValues(alpha: 0.6)),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ListsPage extends StatefulWidget {
  final String login;
  final String password;
  final void Function(String listId, String listName) onSearchForList;

  const ListsPage({
    super.key,
    required this.login,
    required this.password,
    required this.onSearchForList,
  });

  @override
  State<ListsPage> createState() => _ListsPageState();
}

class _ListsPageState extends State<ListsPage> {
  final TextEditingController _queryController = TextEditingController();
  final List<_ShoppingList> _lists = [];
  bool _isLoading = true;
  bool _showAddedLists = false;



  @override
  void initState() {
    super.initState();
    _loadOrMigrate();
  }

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> refresh() => _loadOrMigrate();

  Future<void> _loadOrMigrate() async {
    setState(() => _isLoading = true);
    try {
      final apiLists = await ApiService.instance.getLists();
      if (!mounted) return;
      setState(() {
        _lists
          ..clear()
          ..addAll(apiLists.map((l) => _ShoppingList.fromApi(l)));
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки списков: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  List<_ShoppingList> _filtered() {
    final q = _normalizeQuery(_queryController.text);
    final visible = _showAddedLists
        ? _lists.where((l) => !l.isOwner && l.role != 'owner').toList()
        : _lists.where((l) => l.isOwner || l.role == 'owner').toList();
    if (q.isEmpty) return visible;
    return visible.where((l) => _normalizeQuery(l.name).contains(q)).toList();
  }

  Future<void> _addListDialog() async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          title: const Text('Новый список', style: TextStyle(color: Colors.white)),
          content: TextField(
            controller: controller,
            autofocus: true,
            style: const TextStyle(color: Colors.white),
            textInputAction: TextInputAction.done,
            decoration: InputDecoration(
              hintText: 'Название списка',
              hintStyle: const TextStyle(color: Colors.white54),
              filled: true,
              fillColor: Colors.black.withValues(alpha: 0.15),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _authBlue, width: 1.5),
              ),
            ),
            onSubmitted: (v) => Navigator.pop(context, v),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Отмена', style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(context, controller.text),
              style: ElevatedButton.styleFrom(
                backgroundColor: _authBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text('Добавить'),
            ),
          ],
        );
      },
    );
    final name = (result ?? '').trim();
    if (name.isEmpty) return;

    try {
      final created = await ApiService.instance.createList(name);
      if (!mounted) return;
      setState(() {
        _lists.insert(0, _ShoppingList.fromApi(created));
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Не удалось создать список: $e')),
        );
      }
    }
  }

  Future<void> _showShareDialog(_ShoppingList list) async {
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

  Widget _buildListsTab(String title, bool isAdded) {
    final selected = _showAddedLists == isAdded;
    return InkWell(
      onTap: () => setState(() => _showAddedLists = isAdded),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: GoogleFonts.inter(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 6),
          Container(
            height: 1.5,
            width: isAdded ? 126 : 88,
            color: selected ? Colors.white70 : Colors.white54,
          ),
        ],
      ),
    );
  }

  Widget _buildListCard(_ShoppingList list) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: InkWell(
        borderRadius: BorderRadius.circular(8),
        onTap: () => _openList(list),
        child: Container(
          height: 44,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: _authBlue, width: 2),
          ),
          padding: const EdgeInsets.only(left: 24, right: 8),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  list.name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: GoogleFonts.inter(
                    color: Colors.black,
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              IconButton(
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
                ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _toggleFavorite(_ShoppingList list) async {
    if (list.isSystem) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Системный список «⭐ Избранное» закреплен в избранном')),
      );
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Товары можно сохранять в системный список «⭐ Избранное»')),
    );
  }

  Future<void> _deleteList(_ShoppingList list) async {
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
  }

  Future<void> _openList(_ShoppingList list) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ListDetailsPage(
          listId: list.id,
          listTitle: list.name,
          onSearchForList: widget.onSearchForList,
        ),
      ),
    );
    await refresh();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered();
    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
              child: Column(
                children: [
                  TextField(
                    controller: _queryController,
                    onChanged: (_) => setState(() {}),
                    decoration: InputDecoration(
                      hintText: 'Поиск',
                      prefixIcon: const Icon(Icons.search, color: _authBlue),
                      filled: true,
                      fillColor: Colors.white,
                      hintStyle: const TextStyle(color: Colors.black38),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: const BorderSide(color: _authBlue, width: 1.5),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: const BorderSide(color: _authBlue, width: 1.5),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: const BorderSide(color: _authBlue, width: 2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      _buildListsTab('Мои списки', false),
                      const SizedBox(width: 18),
                      _buildListsTab('Добавленные списки', true),
                    ],
                  ),
                  const SizedBox(height: 14),
                  Expanded(
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
                    SizedBox(
                      width: double.infinity,
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
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ListDetailsPage extends StatefulWidget {
  final String listId;
  final String? listTitle;
  final void Function(String listId, String listName)? onSearchForList;

  const ListDetailsPage({
    super.key,
    required this.listId,
    this.listTitle,
    this.onSearchForList,
  });

  @override
  State<ListDetailsPage> createState() => _ListDetailsPageState();
}

class _ListDetailsPageState extends State<ListDetailsPage> {
  final TextEditingController _itemController = TextEditingController();
  _ShoppingList? _list;
  bool _isLoading = true;
  List<ApiItemSuggestion> _suggestions = [];





  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _itemController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _isLoading = true);
    try {
      final detailFuture = ApiService.instance.getListDetail(widget.listId);
      final suggestionsFuture = ApiService.instance.getListSuggestions(widget.listId);

      final detail = await detailFuture;
      final apiList = detail['list'] as ApiShoppingList;
      final apiItems = detail['items'] as List<ApiShoppingItem>;
      final suggestions = await suggestionsFuture.catchError((_) => <ApiItemSuggestion>[]);

      if (!mounted) return;
      setState(() {
        _list = _ShoppingList.fromApi(
          apiList,
          apiItems.map(_ShoppingItem.fromApi).toList(),
        );
        _suggestions = suggestions;
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки списка: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _addSuggestedItem(String name) async {
    try {
      final res = await ApiService.instance.addItem(widget.listId, name);
      final newItem = _ShoppingItem.fromApi(res.item);
      if (!mounted) return;
      setState(() {
        _list = _list?.copyWith(items: [newItem, ...?_list?.items]);
        _suggestions = res.suggestions;
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Widget _buildSuggestionsBanner() {
    if (_suggestions.isEmpty) return const SizedBox.shrink();
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 0, 20, 12),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: _authCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _authBlue.withValues(alpha: 0.35), width: 1.2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.auto_awesome, color: _authBlue, size: 16),
              const SizedBox(width: 6),
              Text(
                'Часто покупают вместе:',
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: Colors.white70,
                ),
              ),
              const Spacer(),
              InkWell(
                onTap: () => setState(() => _suggestions = []),
                child: const Icon(Icons.close, color: Colors.white38, size: 16),
              ),
            ],
          ),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: _suggestions.map((s) {
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ActionChip(
                    avatar: const Icon(Icons.add, size: 15, color: _authBlue),
                    label: Text(capName(s.name), style: const TextStyle(color: Colors.white, fontSize: 13)),
                    backgroundColor: Colors.black.withValues(alpha: 0.25),
                    side: BorderSide(color: _authBlue.withValues(alpha: 0.45)),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    onPressed: () => _addSuggestedItem(capName(s.name)),
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _renameListDialog() async {
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
  }

  bool _isAddingItem = false;

  Future<void> _addItemWithText(String text) async {
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
  }

  Future<void> _clearItems({required bool checkedOnly}) async {
    final title = checkedOnly ? 'Очистить купленные' : 'Очистить весь список';
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _authCard,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        title: Text(title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: Text(
          checkedOnly
              ? 'Удалить из этого списка все отмеченные галочкой товары?'
              : 'Удалить абсолютно все товары из этого списка?',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Отмена', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: _danger,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
            ),
            child: const Text('Удалить'),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    try {
      final res = await ApiService.instance.clearItems(widget.listId, checkedOnly: checkedOnly);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Удалено товаров: $res')),
      );
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Ошибка очистки: $e')));
      }
    }
  }

  Future<void> _toggleItem(int index, bool? value) async {
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
  }

  Future<void> _removeItem(int index) async {
    final current = _list;
    if (current == null || index >= current.items.length) return;
    final item = current.items[index];
    try {
      await ApiService.instance.deleteItem(widget.listId, item.id);
      if (!mounted) return;
      final items = [...current.items]..removeAt(index);
      setState(() => _list = current.copyWith(items: items));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _showAddItemDialog() async {
    _itemController.clear();
    await showDialog<void>(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: _authCard,
          title: const Text('Добавить товар', style: TextStyle(color: Colors.white)),
          content: TextField(
            controller: _itemController,
            autofocus: true,
            style: const TextStyle(color: Colors.white),
            textInputAction: TextInputAction.done,
            onSubmitted: (val) async {
              final text = val.trim();
              if (text.isNotEmpty) {
                Navigator.pop(context);
                await _addItemWithText(text);
              }
            },
            decoration: InputDecoration(
              hintText: 'Название товара',
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
              onPressed: () async {
                final text = _itemController.text.trim();
                if (text.isNotEmpty) {
                  Navigator.pop(context);
                  await _addItemWithText(text);
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: _authBlue,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text('Добавить'),
            ),
          ],
        );
      },
    );
  }

  Future<void> _showSearchAddSheet() async {
    final current = _list;
    if (current == null) return;

    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) {
        final controller = TextEditingController();
        final focusNode = FocusNode();



        return Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Container(
            decoration: BoxDecoration(
              color: _authCard,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(22)),
              border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
            ),
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            child: SafeArea(
              top: false,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 46,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.white24,
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Добавить через поиск',
                          style: GoogleFonts.inter(
                            fontSize: 16,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                      ),
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        style: TextButton.styleFrom(foregroundColor: Colors.white70),
                        child: const Text('Закрыть'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Autocomplete<ApiCatalogProduct>(
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
                        final res = await ApiService.instance.addItem(widget.listId, capName(product.name));
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
                                                capName(option.name),
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
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final current = _list;
    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          SafeArea(
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
                : current == null
                ? const Center(
              child: Text('Список не найден', style: TextStyle(color: Colors.white70)),
            )
                : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 10, 20, 10),
                  child: Row(
                    children: [
                      IconButton(
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.arrow_back),
                        color: Colors.white70,
                      ),
                      Expanded(
                        child: Text(
                          current.name,
                          style: GoogleFonts.inter(
                            fontSize: 18,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                          ),
                        ),
                      ),
                      if (!current.isSystem)
                        IconButton(
                          onPressed: _renameListDialog,
                          icon: const Icon(Icons.edit_outlined),
                          color: Colors.white70,
                        ),
                      IconButton(
                        onPressed: _toggleFavorite,
                        icon: Icon(
                          current.isFavorite ? Icons.favorite : Icons.favorite_border,
                        ),
                        color: _authBlue,
                      ),
                      IconButton(
                        onPressed: () {
                          final goToSearch = widget.onSearchForList;
                          if (goToSearch != null) {
                            final name = _list?.name ?? widget.listTitle ?? 'Список';
                            Navigator.pop(context);
                            goToSearch(widget.listId, name);
                          } else {
                            _showSearchAddSheet();
                          }
                        },
                        icon: const Icon(Icons.search),
                        color: Colors.white70,
                      ),
                      IconButton(
                        onPressed: _showAddItemDialog,
                        icon: const Icon(Icons.add_circle_outline),
                        color: Colors.white70,
                      ),
                      PopupMenuButton<String>(
                        icon: const Icon(Icons.more_vert, color: Colors.white70),
                        color: _authCard,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                        onSelected: (val) {
                          if (val == 'clear_checked') {
                            _clearItems(checkedOnly: true);
                          } else if (val == 'clear_all') {
                            _clearItems(checkedOnly: false);
                          }
                        },
                        itemBuilder: (ctx) => [
                          const PopupMenuItem(
                            value: 'clear_checked',
                            child: Row(
                              children: [
                                Icon(Icons.remove_done, color: Colors.white70, size: 18),
                                SizedBox(width: 8),
                                Text('Очистить купленные', style: TextStyle(color: Colors.white)),
                              ],
                            ),
                          ),
                          const PopupMenuItem(
                            value: 'clear_all',
                            child: Row(
                              children: [
                                Icon(Icons.delete_sweep, color: _danger, size: 18),
                                SizedBox(width: 8),
                                Text('Очистить весь список', style: TextStyle(color: _danger)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                _buildSuggestionsBanner(),
                Expanded(
                  child: current.items.isEmpty
                      ? const Center(
                    child: Text(
                      'Товаров пока нет',
                      style: TextStyle(color: Colors.white70),
                    ),
                  )
                      : ListView.builder(
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                    itemCount: current.items.length,
                    itemBuilder: (context, index) {
                      final item = current.items[index];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Dismissible(
                          key: ValueKey(item.id),
                          direction: DismissDirection.endToStart,
                          onDismissed: (_) => _removeItem(index),
                          background: Container(
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.only(right: 20),
                            decoration: BoxDecoration(
                              color: _danger.withValues(alpha: 0.9),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: const Icon(Icons.delete, color: Colors.white),
                          ),
                          child: Container(
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: _authBlue, width: 1.6),
                            ),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 8,
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        capName(item.name),
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
                                ),
                                Checkbox(
                                  value: item.isDone,
                                  onChanged: (v) => _toggleItem(index, v),
                                  activeColor: _authBlue,
                                  checkColor: Colors.white,
                                  side: const BorderSide(color: _authBlue, width: 1.4),
                                ),
                                IconButton(
                                  onPressed: () => _removeItem(index),
                                  icon: const Icon(Icons.delete_outline),
                                  color: _authBlue,
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ProfileTab extends StatefulWidget {
  final String login;
  final VoidCallback onOpenListsTab;

  const _ProfileTab({
    required this.login,
    required this.onOpenListsTab,
  });

  @override
  State<_ProfileTab> createState() => _ProfileTabState();
}

class _ProfileTabState extends State<_ProfileTab> {
  late final TextEditingController _nameController;
  final GlobalKey<NavigatorState> _navKey = GlobalKey<NavigatorState>();
  ApiUserSettings? _settings;
  ApiUserProfile? _profile;
  // ignore: unused_field
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.login);
    _loadAll();
  }

  Future<void> _loadAll() async {
    setState(() => _isLoading = true);
    try {
      final results = await Future.wait([
        ApiService.instance.getUserSettings().catchError(
          (_) => ApiUserSettings(aiSuggestionsEnabled: true, suggestionsLimit: 5, aiAvailable: true),
        ),
        ApiService.instance.getMe().catchError(
          (_) => ApiUserProfile(
            id: '',
            email: widget.login,
            displayName: widget.login,
            createdAt: DateTime.now(),
          ),
        ),
      ]);
      if (!mounted) return;
      setState(() {
        _settings = results[0] as ApiUserSettings;
        _profile = results[1] as ApiUserProfile;
        final dName = _profile?.displayName ?? '';
        _nameController.text = dName.isNotEmpty ? dName : (_profile?.email ?? widget.login);
        _isLoading = false;
      });
    } catch (_) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _toggleAi(bool val) async {
    try {
      final s = await ApiService.instance.updateUserSettings(aiSuggestionsEnabled: val);
      if (mounted) setState(() => _settings = s);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка настроек: $e')),
        );
      }
    }
  }

  Future<void> _openFavoritesList() async {
    try {
      final apiList = await ApiService.instance.getFavoritesList();
      if (!mounted) return;
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ListDetailsPage(
            listId: apiList.id,
            listTitle: apiList.name,
          ),
        ),
      );
      await _loadAll();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Не удалось открыть избранное: $e')),
        );
      }
    }
  }

  Future<void> _showSessionsSheet() async {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) {
        return Container(
          decoration: BoxDecoration(
            color: _authCard,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            border: Border.all(color: _authBlue.withValues(alpha: 0.4), width: 1.5),
          ),
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          child: SafeArea(
            top: false,
            child: FutureBuilder<List<ApiUserSession>>(
              future: ApiService.instance.getSessions(),
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
                        const Icon(Icons.devices, color: _authBlue, size: 22),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Активные сессии (БД)',
                            style: GoogleFonts.inter(
                              fontSize: 18,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        IconButton(
                          onPressed: () => Navigator.pop(ctx),
                          icon: const Icon(Icons.close, color: Colors.white60, size: 20),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Список подключенных устройств из таблицы user_sessions:',
                      style: TextStyle(color: Colors.white60, fontSize: 13),
                    ),
                    const SizedBox(height: 16),
                    if (snapshot.connectionState == ConnectionState.waiting)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 36),
                        child: Center(child: CircularProgressIndicator(color: _authBlue)),
                      )
                    else if (snapshot.hasError)
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text('Ошибка: ${snapshot.error}', style: const TextStyle(color: _danger)),
                      )
                    else if (snapshot.data == null || snapshot.data!.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 24),
                        child: Text('Нет активных сессий', style: TextStyle(color: Colors.white70)),
                      )
                    else
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxHeight: 320),
                        child: ListView.separated(
                          shrinkWrap: true,
                          itemCount: snapshot.data!.length,
                          separatorBuilder: (_, _) => const SizedBox(height: 8),
                          itemBuilder: (context, index) {
                            final sess = snapshot.data![index];
                            return Container(
                              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                  color: sess.isCurrent ? _authBlue : Colors.black12,
                                  width: sess.isCurrent ? 2 : 1,
                                ),
                              ),
                              child: Row(
                                children: [
                                  Icon(
                                    sess.userAgent?.contains('Mobile') == true
                                        ? Icons.smartphone
                                        : Icons.computer,
                                    color: _authBlue,
                                    size: 24,
                                  ),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Expanded(
                                              child: Text(
                                                sess.userAgent ?? 'Устройство',
                                                maxLines: 1,
                                                overflow: TextOverflow.ellipsis,
                                                style: const TextStyle(
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 13,
                                                  color: _ink,
                                                ),
                                              ),
                                            ),
                                            if (sess.isCurrent)
                                              Container(
                                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                                decoration: BoxDecoration(
                                                  color: _authBlue.withValues(alpha: 0.15),
                                                  borderRadius: BorderRadius.circular(6),
                                                ),
                                                child: const Text(
                                                  'Текущая',
                                                  style: TextStyle(
                                                    fontSize: 10,
                                                    fontWeight: FontWeight.bold,
                                                    color: _authBlueDark,
                                                  ),
                                                ),
                                              ),
                                          ],
                                        ),
                                        const SizedBox(height: 3),
                                        Text(
                                          'Вход: ${sess.issuedAt.day.toString().padLeft(2, '0')}.${sess.issuedAt.month.toString().padLeft(2, '0')}.${sess.issuedAt.year} ${sess.issuedAt.hour}:${sess.issuedAt.minute.toString().padLeft(2, '0')}',
                                          style: const TextStyle(fontSize: 11, color: _muted),
                                        ),
                                      ],
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
  }

  Future<void> _showChangePasswordDialog() async {
    final oldController = TextEditingController();
    final newController = TextEditingController();
    final confirmController = TextEditingController();
    bool isSubmitting = false;

    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: _authCard,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              title: const Text(
                'Смена пароля',
                style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: oldController,
                      obscureText: true,
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        labelText: 'Текущий пароль',
                        labelStyle: const TextStyle(color: Colors.white70),
                        filled: true,
                        fillColor: Colors.black.withValues(alpha: 0.25),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: newController,
                      obscureText: true,
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        labelText: 'Новый пароль (от 8 символов)',
                        labelStyle: const TextStyle(color: Colors.white70),
                        filled: true,
                        fillColor: Colors.black.withValues(alpha: 0.25),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: confirmController,
                      obscureText: true,
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        labelText: 'Повторите новый пароль',
                        labelStyle: const TextStyle(color: Colors.white70),
                        filled: true,
                        fillColor: Colors.black.withValues(alpha: 0.25),
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: isSubmitting ? null : () => Navigator.pop(ctx),
                  child: const Text('Отмена', style: TextStyle(color: Colors.white60)),
                ),
                ElevatedButton(
                  onPressed: isSubmitting
                      ? null
                      : () async {
                          final oldP = oldController.text.trim();
                          final newP = newController.text.trim();
                          final confP = confirmController.text.trim();

                          if (oldP.isEmpty || newP.isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Заполните все поля')),
                            );
                            return;
                          }
                          if (newP.length < 8) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Новый пароль должен быть от 8 символов')),
                            );
                            return;
                          }
                          if (newP != confP) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('Пароли не совпадают')),
                            );
                            return;
                          }

                          setDialogState(() => isSubmitting = true);
                          try {
                            await ApiService.instance.changePassword(
                              currentPassword: oldP,
                              newPassword: newP,
                            );
                            if (ctx.mounted) Navigator.pop(ctx);
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Пароль успешно изменен')),
                              );
                            }
                          } catch (e) {
                            setDialogState(() => isSubmitting = false);
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(content: Text('Ошибка: $e')),
                              );
                            }
                          }
                        },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _authBlue,
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                  child: isSubmitting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                        )
                      : const Text('Изменить'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        final canPop = _navKey.currentState?.canPop() ?? false;
        if (canPop) {
          _navKey.currentState?.pop();
        } else {
          Navigator.of(context).maybePop();
        }
      },
      child: Navigator(
        key: _navKey,
        onGenerateRoute: (settings) {
          return MaterialPageRoute(
            settings: settings,
            builder: (context) => _ProfileHomeView(
              login: widget.login,
              profile: _profile,
              nameController: _nameController,
              aiSuggestionsEnabled: _settings?.aiSuggestionsEnabled ?? true,
              onToggleAiSuggestions: _toggleAi,
              onFavorites: _openFavoritesList,
              onSessions: _showSessionsSheet,
              onChangePassword: _showChangePasswordDialog,
              onHistory: () => _navKey.currentState?.push(
                MaterialPageRoute(
                  builder: (_) => _ProfileListsView(
                    title: 'История списков',
                    onOpenListsTab: widget.onOpenListsTab,
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ProfileHomeView extends StatelessWidget {
  final String login;
  final ApiUserProfile? profile;
  final TextEditingController nameController;
  final bool aiSuggestionsEnabled;
  final ValueChanged<bool> onToggleAiSuggestions;
  final VoidCallback onFavorites;
  final VoidCallback onSessions;
  final VoidCallback onChangePassword;
  final VoidCallback onHistory;

  const _ProfileHomeView({
    required this.login,
    required this.profile,
    required this.nameController,
    required this.aiSuggestionsEnabled,
    required this.onToggleAiSuggestions,
    required this.onFavorites,
    required this.onSessions,
    required this.onChangePassword,
    required this.onHistory,
  });

  @override
  Widget build(BuildContext context) {
    final created = profile?.createdAt;
    final regDate = created != null
        ? '${created.day.toString().padLeft(2, '0')}.${created.month.toString().padLeft(2, '0')}.${created.year}'
        : '–';

    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
              child: Column(
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: _authBlue.withValues(alpha: 0.18),
                          shape: BoxShape.circle,
                          border: Border.all(color: _authBlue, width: 2),
                        ),
                        child: const Icon(
                          Icons.person,
                          size: 38,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              profile?.displayName.isNotEmpty == true
                                  ? profile!.displayName
                                  : login,
                              style: GoogleFonts.inter(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              profile?.email.isNotEmpty == true ? profile!.email : login,
                              style: const TextStyle(color: Colors.white60, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: _authCard,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: _authBlue.withValues(alpha: 0.35)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: _buildStatItem(
                                '${profile?.listsCount ?? 0}',
                                'Списков',
                                Icons.format_list_bulleted,
                              ),
                            ),
                            Container(width: 1, height: 36, color: Colors.white12),
                            Expanded(
                              child: _buildStatItem(
                                '${profile?.itemsCount ?? 0}',
                                'Товаров',
                                Icons.shopping_basket_outlined,
                              ),
                            ),
                            Container(width: 1, height: 36, color: Colors.white12),
                            Expanded(
                              child: _buildStatItem(
                                regDate,
                                'Регистрация',
                                Icons.calendar_today_outlined,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
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
                                'Подсказки «часто берут»',
                                style: GoogleFonts.inter(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                  fontSize: 13,
                                ),
                              ),
                              const SizedBox(height: 2),
                              const Text(
                                'Рекомендации сопутствующих товаров по правилам ассоциаций',
                                style: TextStyle(color: Colors.white60, fontSize: 11),
                              ),
                            ],
                          ),
                        ),
                        Switch(
                          value: aiSuggestionsEnabled,
                          // ignore: deprecated_member_use
                          activeColor: _authBlue,
                          onChanged: onToggleAiSuggestions,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  _ProfileActionButton(
                    icon: Icons.star,
                    label: '⭐ Системное Избранное',
                    subtitle: 'Открыть системный список покупок',
                    onPressed: onFavorites,
                  ),
                  const SizedBox(height: 12),
                  _ProfileActionButton(
                    icon: Icons.history,
                    label: 'История списков',
                    subtitle: 'Все списки и управление ими',
                    onPressed: onHistory,
                  ),
                  const SizedBox(height: 12),
                  _ProfileActionButton(
                    icon: Icons.devices,
                    label: 'Активные сессии (устройства)',
                    subtitle: 'Список авторизованных сессий в БД',
                    onPressed: onSessions,
                  ),
                  const SizedBox(height: 12),
                  _ProfileActionButton(
                    icon: Icons.lock_outline,
                    label: 'Сменить пароль',
                    subtitle: 'Обновить пароль учетной записи',
                    onPressed: onChangePassword,
                  ),
                  const SizedBox(height: 12),
                  _ProfileActionButton(
                    icon: Icons.logout,
                    label: 'Выйти из аккаунта',
                    subtitle: 'Завершить текущую сессию',
                    isDanger: true,
                    onPressed: () async {
                      await ApiService.instance.logout();
                      if (context.mounted) {
                        Navigator.of(context, rootNavigator: true).pushAndRemoveUntil(
                          MaterialPageRoute(builder: (_) => const LoginPage()),
                          (route) => false,
                        );
                      }
                    },
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatItem(String value, String label, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: _authBlue, size: 16),
        const SizedBox(height: 4),
        Text(
          value,
          style: GoogleFonts.inter(
            color: Colors.white,
            fontWeight: FontWeight.w700,
            fontSize: 13,
          ),
          textAlign: TextAlign.center,
        ),
        Text(
          label,
          style: const TextStyle(color: Colors.white54, fontSize: 10),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}

class _ProfileActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final String? subtitle;
  final VoidCallback onPressed;
  final bool isDanger;

  const _ProfileActionButton({
    required this.icon,
    required this.label,
    this.subtitle,
    required this.onPressed,
    this.isDanger = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDanger ? _danger.withValues(alpha: 0.6) : _authBlue,
          width: 1.6,
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: onPressed,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Row(
              children: [
                Icon(
                  icon,
                  color: isDanger ? _danger : _authBlue,
                  size: 22,
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label,
                        style: TextStyle(
                          color: isDanger ? _danger : _ink,
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                        ),
                      ),
                      if (subtitle != null)
                        Text(
                          subtitle!,
                          style: const TextStyle(color: _muted, fontSize: 11),
                        ),
                    ],
                  ),
                ),
                Icon(
                  Icons.chevron_right,
                  color: isDanger ? _danger.withValues(alpha: 0.5) : _muted,
                  size: 20,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ProfileListsView extends StatefulWidget {
  final String title;
  final VoidCallback onOpenListsTab;

  const _ProfileListsView({
    required this.title,
    required this.onOpenListsTab,
  });

  @override
  State<_ProfileListsView> createState() => _ProfileListsViewState();
}

class _ProfileListsViewState extends State<_ProfileListsView> {
  final List<_ShoppingList> _lists = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final apiLists = await ApiService.instance.getLists();
      if (!mounted) return;
      setState(() {
        _lists
          ..clear()
          ..addAll(apiLists.map((l) => _ShoppingList.fromApi(l)));
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка загрузки: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openList(_ShoppingList list) async {
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
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Удаление списка', style: TextStyle(color: Colors.white)),
        content: Text('Удалить список "${list.name}" из базы данных?', style: const TextStyle(color: Colors.white70)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Отмена', style: TextStyle(color: Colors.white60)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: _danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Удалить', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

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
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _authBg,
      body: Stack(
        children: [
          const _AppBackdrop(),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 20),
              child: Column(
                children: [
                  Row(
                    children: [
                      IconButton(
                        onPressed: () => Navigator.pop(context),
                        icon: const Icon(Icons.arrow_back, color: Colors.white70),
                      ),
                      Expanded(
                        child: Column(
                          children: [
                            Text(
                              widget.title,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            const SizedBox(height: 6),
                            Container(height: 2, width: 160, color: Colors.white70),
                          ],
                        ),
                      ),
                      const SizedBox(width: 48),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Expanded(
                    child: _loading
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
                        : _lists.isEmpty
                            ? const Center(
                                child: Text(
                                  'Списков пока нет',
                                  style: TextStyle(color: Colors.white70),
                                ),
                              )
                            : ListView.builder(
                                itemCount: _lists.length,
                                itemBuilder: (context, index) {
                                  final list = _lists[index];
                                  return Padding(
                                    padding: const EdgeInsets.only(bottom: 12),
                                    child: Container(
                                      decoration: BoxDecoration(
                                        color: Colors.white,
                                        borderRadius: BorderRadius.circular(10),
                                        border: Border.all(color: _authBlue, width: 2),
                                      ),
                                      child: InkWell(
                                        borderRadius: BorderRadius.circular(10),
                                        onTap: () => _openList(list),
                                        child: Padding(
                                          padding: const EdgeInsets.symmetric(
                                            horizontal: 14,
                                            vertical: 12,
                                          ),
                                          child: Row(
                                            children: [
                                              Icon(
                                                list.isSystem ? Icons.star : Icons.format_list_bulleted,
                                                color: list.isSystem ? Colors.amber[700] : _authBlue,
                                                size: 22,
                                              ),
                                              const SizedBox(width: 10),
                                              Expanded(
                                                child: Column(
                                                  crossAxisAlignment: CrossAxisAlignment.start,
                                                  children: [
                                                    Text(
                                                      list.name,
                                                      style: const TextStyle(
                                                        color: _ink,
                                                        fontWeight: FontWeight.w700,
                                                        fontSize: 15,
                                                      ),
                                                    ),
                                                    const SizedBox(height: 2),
                                                    Text(
                                                      list.itemCount > 0
                                                          ? '${list.checkedCount}/${list.itemCount} куплено'
                                                          : 'Пустой список',
                                                      style: const TextStyle(
                                                        color: _muted,
                                                        fontSize: 12,
                                                      ),
                                                    ),
                                                  ],
                                                ),
                                              ),
                                              if (!list.isSystem)
                                                IconButton(
                                                  onPressed: () => _delete(list),
                                                  icon: const Icon(Icons.delete_outline),
                                                  color: _danger,
                                                  tooltip: 'Удалить список',
                                                ),
                                              const Icon(Icons.chevron_right, color: _muted, size: 20),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  );
                                },
                              ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ShoppingItem {
  final String id;
  final String name;
  final bool isDone;
  final DateTime createdAt;
  final double quantity;
  final String? unit;
  final String? notes;

  _ShoppingItem({
    required this.name,
  })  : id = DateTime.now().microsecondsSinceEpoch.toString(),
        isDone = false,
        createdAt = DateTime.now(),
        quantity = 1.0,
        unit = null,
        notes = null;

  _ShoppingItem._({
    required this.id,
    required this.name,
    required this.isDone,
    required this.createdAt,
    this.quantity = 1.0,
    this.unit,
    this.notes,
  });

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
    bool? isDone,
    String? name,
    double? quantity, 
    String? unit,
    String? notes,
  }) {
    return _ShoppingItem._(
      id: id,
      name: name ?? this.name,
      isDone: isDone ?? this.isDone,
      createdAt: createdAt,
      quantity: quantity ?? this.quantity,
      unit: unit ?? this.unit,
      notes: notes ?? this.notes,
    );
  }

}
