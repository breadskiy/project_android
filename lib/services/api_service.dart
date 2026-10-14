import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiException implements Exception {
  final String message;
  final int statusCode;

  ApiException(this.message, {this.statusCode = 0});

  @override
  String toString() => message;
}

class ApiUser {
  final String id;
  final String email;
  final String displayName;

  ApiUser({
    required this.id,
    required this.email,
    required this.displayName,
  });

  factory ApiUser.fromJson(Map<String, dynamic> json) {
    return ApiUser(
      id: json['id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      displayName: json['display_name']?.toString() ?? 'Пользователь',
    );
  }
}

double parseApiDouble(dynamic val, [double fallback = 0.0]) {
  if (val == null) return fallback;
  if (val is num) return val.toDouble();
  if (val is String) return double.tryParse(val) ?? fallback;
  return fallback;
}

int parseApiInt(dynamic val, [int fallback = 0]) {
  if (val == null) return fallback;
  if (val is num) return val.toInt();
  if (val is String) return int.tryParse(val) ?? fallback;
  return fallback;
}

class ApiShoppingList {
  final String id;
  final String name;
  final String? description;
  final bool isOwner;
  final bool isShared;
  final bool isSystem;
  final String role;
  final int itemCount;
  final int checkedCount;
  final DateTime createdAt;

  ApiShoppingList({
    required this.id,
    required this.name,
    this.description,
    required this.isOwner,
    required this.isShared,
    required this.isSystem,
    required this.role,
    required this.itemCount,
    required this.checkedCount,
    required this.createdAt,
  });

  factory ApiShoppingList.fromJson(Map<String, dynamic> json) {
    return ApiShoppingList(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Список',
      description: json['description']?.toString(),
      isOwner: json['is_owner'] == true,
      isShared: json['is_shared'] == true,
      isSystem: json['is_system'] == true,
      role: json['role']?.toString() ?? 'owner',
      itemCount: parseApiInt(json['item_count']),
      checkedCount: parseApiInt(json['checked_count']),
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class ApiShoppingItem {
  final String id;
  final String name;
  final double quantity;
  final String? unit;
  final String? notes;
  final int priority;
  final bool checked;
  final DateTime addedAt;

  ApiShoppingItem({
    required this.id,
    required this.name,
    required this.quantity,
    this.unit,
    this.notes,
    required this.priority,
    required this.checked,
    required this.addedAt,
  });

  factory ApiShoppingItem.fromJson(Map<String, dynamic> json) {
    return ApiShoppingItem(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? 'Товар',
      quantity: parseApiDouble(json['quantity'], 1.0),
      unit: json['unit']?.toString(),
      notes: json['notes']?.toString(),
      priority: parseApiInt(json['priority'], 1),
      checked: json['checked'] == true,
      addedAt: json['added_at'] != null
          ? DateTime.tryParse(json['added_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
    );
  }
}

class ApiItemSuggestion {
  final String name;
  final String? productId;
  final double score;

  ApiItemSuggestion({
    required this.name,
    this.productId,
    required this.score,
  });

  factory ApiItemSuggestion.fromJson(Map<String, dynamic> json) {
    return ApiItemSuggestion(
      name: json['name']?.toString() ?? '',
      productId: json['product_id']?.toString(),
      score: parseApiDouble(json['score']),
    );
  }
}

class ApiAddResult {
  final ApiShoppingItem item;
  final List<ApiItemSuggestion> suggestions;

  ApiAddResult({
    required this.item,
    required this.suggestions,
  });
}

class ApiCatalogProduct {
  final String id;
  final String name;
  final String? normalizedName;
  final String? categoryName;
  final String? defaultUnit;
  final int popularity;
  final String? matchedAlias;

  ApiCatalogProduct({
    required this.id,
    required this.name,
    this.normalizedName,
    this.categoryName,
    this.defaultUnit,
    required this.popularity,
    this.matchedAlias,
  });

  factory ApiCatalogProduct.fromJson(Map<String, dynamic> json) {
    return ApiCatalogProduct(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      normalizedName: json['normalized_name']?.toString(),
      categoryName: json['category_name']?.toString(),
      defaultUnit: json['default_unit']?.toString(),
      popularity: parseApiInt(json['popularity']),
      matchedAlias: json['matched_alias']?.toString(),
    );
  }
}

class ApiInviteInfo {
  final String code;
  final String link;
  final String qrSvgUrl;
  final String mode;
  final String role;

  ApiInviteInfo({
    required this.code,
    required this.link,
    required this.qrSvgUrl,
    required this.mode,
    required this.role,
  });

  factory ApiInviteInfo.fromJson(Map<String, dynamic> json) {
    return ApiInviteInfo(
      code: json['code']?.toString() ?? '',
      link: json['link']?.toString() ?? '',
      qrSvgUrl: json['qr_svg_url']?.toString() ?? '',
      mode: json['mode']?.toString() ?? 'share',
      role: json['role']?.toString() ?? 'editor',
    );
  }
}

class ApiReplenishItem {
  final String name;
  final String normalizedName;
  final int purchases;
  final double avgIntervalDays;
  final double daysSinceLast;

  ApiReplenishItem({
    required this.name,
    required this.normalizedName,
    required this.purchases,
    required this.avgIntervalDays,
    required this.daysSinceLast,
  });

  factory ApiReplenishItem.fromJson(Map<String, dynamic> json) {
    return ApiReplenishItem(
      name: json['name']?.toString() ?? '',
      normalizedName: json['normalized_name']?.toString() ?? '',
      purchases: parseApiInt(json['purchases']),
      avgIntervalDays: parseApiDouble(json['avg_interval_days']),
      daysSinceLast: parseApiDouble(json['days_since_last']),
    );
  }
}

class ApiUserSettings {
  final bool aiSuggestionsEnabled;
  final int suggestionsLimit;
  final bool aiAvailable;

  ApiUserSettings({
    required this.aiSuggestionsEnabled,
    required this.suggestionsLimit,
    required this.aiAvailable,
  });

  factory ApiUserSettings.fromJson(Map<String, dynamic> json) {
    return ApiUserSettings(
      aiSuggestionsEnabled: json['ai_suggestions_enabled'] == true,
      suggestionsLimit: parseApiInt(json['suggestions_limit'], 5),
      aiAvailable: json['ai_available'] == true,
    );
  }
}

class ApiCategory {
  final String id;
  final String name;
  final int productCount;

  ApiCategory({
    required this.id,
    required this.name,
    required this.productCount,
  });

  factory ApiCategory.fromJson(Map<String, dynamic> json) {
    return ApiCategory(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      productCount: parseApiInt(json['product_count']),
    );
  }
}

class ApiParsedItem {
  final String name;
  final double quantity;
  final String? unit;

  ApiParsedItem({required this.name, required this.quantity, this.unit});

  factory ApiParsedItem.fromJson(Map<String, dynamic> json) {
    return ApiParsedItem(
      name: json['name']?.toString() ?? '',
      quantity: parseApiDouble(json['quantity'], 1.0),
      unit: json['unit']?.toString(),
    );
  }
}

class ApiUserSession {
  final String id;
  final String? userAgent;
  final DateTime issuedAt;
  final DateTime expiresAt;
  final bool isCurrent;

  ApiUserSession({
    required this.id,
    this.userAgent,
    required this.issuedAt,
    required this.expiresAt,
    this.isCurrent = false,
  });

  DateTime get createdAt => issuedAt;

  factory ApiUserSession.fromJson(Map<String, dynamic> json) {
    return ApiUserSession(
      id: json['id']?.toString() ?? '',
      userAgent: json['user_agent']?.toString(),
      issuedAt: json['issued_at'] != null
          ? DateTime.tryParse(json['issued_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      expiresAt: json['expires_at'] != null
          ? DateTime.tryParse(json['expires_at'].toString()) ?? DateTime.now()
          : DateTime.now(),
      isCurrent: json['current'] == true,
    );
  }
}

class ApiUserProfile {
  final String id;
  final String email;
  final String displayName;
  final DateTime? createdAt;
  final DateTime? lastLogin;
  final int listsOwned;
  final int listsShared;
  final int itemsTotal;

  int get listsCount => listsOwned + listsShared;
  int get itemsCount => itemsTotal;

  ApiUserProfile({
    required this.id,
    required this.email,
    required this.displayName,
    this.createdAt,
    this.lastLogin,
    this.listsOwned = 0,
    this.listsShared = 0,
    this.itemsTotal = 0,
  });

  factory ApiUserProfile.fromJson(Map<String, dynamic> json) {
    final stats = json['stats'] is Map<String, dynamic> ? json['stats'] as Map<String, dynamic> : <String, dynamic>{};
    return ApiUserProfile(
      id: json['id']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      displayName: json['display_name']?.toString() ?? 'Пользователь',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
      lastLogin: json['last_login'] != null
          ? DateTime.tryParse(json['last_login'].toString())
          : null,
      listsOwned: parseApiInt(stats['lists_owned']),
      listsShared: parseApiInt(stats['lists_shared']),
      itemsTotal: parseApiInt(stats['items_total']),
    );
  }
}

class ApiService {
  static final ApiService instance = ApiService._internal();
  ApiService._internal();

  static const _timeout = Duration(seconds: 20);

  Future<http.Response> _wrapRequest(Future<http.Response> Function() fn) async {
    try {
      return await fn().timeout(_timeout);
    } on TimeoutException {
      throw ApiException(
        'Превышено время ожидания сервера ($baseUrl). Проверьте, запущен ли бэкенд.',
      );
    } on SocketException catch (e) {
      throw ApiException(
        'Не удалось подключиться к серверу ($baseUrl). Проверьте запуск бэкенда: ${e.message}',
      );
    } catch (e) {
      if (e is ApiException) rethrow;
      throw ApiException('Ошибка соединения: $e');
    }
  }

  static const String _prefAccessToken = 'api_access_token';
  static const String _prefRefreshToken = 'api_refresh_token';
  static const String _prefUserId = 'api_user_id';
  static const String _prefUserEmail = 'api_user_email';
  static const String _prefUserDisplayName = 'api_user_display_name';

  String? _accessToken;
  String? _refreshToken;
  ApiUser? _currentUser;

  bool get isLoggedIn => _accessToken != null && _accessToken!.isNotEmpty;
  ApiUser? get currentUser => _currentUser;

  String get baseUrl {
    if (kIsWeb) return 'http://127.0.0.1:8000';
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://127.0.0.1:8000';
  }

  static String normalizeEmail(String input) {
    final trimmed = input.trim();
    if (trimmed.contains('@')) return trimmed.toLowerCase();

    const cyr = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя';
    const lat = [
      'a', 'b', 'v', 'g', 'd', 'e', 'yo', 'zh', 'z', 'i', 'y', 'k', 'l', 'm',
      'n', 'o', 'p', 'r', 's', 't', 'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch',
      '', 'y', '', 'e', 'yu', 'ya'
    ];
    var safe = trimmed.toLowerCase();
    for (var i = 0; i < cyr.length; i++) {
      safe = safe.replaceAll(cyr[i], lat[i]);
    }
    safe = safe.replaceAll(RegExp(r'[^a-z0-9._\-]'), '');
    if (safe.isEmpty) safe = 'user${DateTime.now().millisecondsSinceEpoch % 10000}';
    return '$safe@smartlist.local';
  }

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _accessToken = prefs.getString(_prefAccessToken);
    _refreshToken = prefs.getString(_prefRefreshToken);

    final id = prefs.getString(_prefUserId);
    final email = prefs.getString(_prefUserEmail);
    final name = prefs.getString(_prefUserDisplayName);

    if (id != null && email != null) {
      _currentUser = ApiUser(
        id: id,
        email: email,
        displayName: name ?? 'Пользователь',
      );
    }
  }

  Future<void> _saveTokens({
    required String accessToken,
    required String refreshToken,
    ApiUser? user,
  }) async {
    _accessToken = accessToken;
    _refreshToken = refreshToken;
    if (user != null) _currentUser = user;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefAccessToken, accessToken);
    await prefs.setString(_prefRefreshToken, refreshToken);
    if (_currentUser != null) {
      await prefs.setString(_prefUserId, _currentUser!.id);
      await prefs.setString(_prefUserEmail, _currentUser!.email);
      await prefs.setString(_prefUserDisplayName, _currentUser!.displayName);
    }
  }

  Future<void> logout() async {
    if (_refreshToken != null) {
      try {
        await http.post(
          Uri.parse('$baseUrl/auth/logout'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh_token': _refreshToken}),
        );
      } catch (_) {
        // Best effort
      }
    }

    _accessToken = null;
    _refreshToken = null;
    _currentUser = null;

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefAccessToken);
    await prefs.remove(_prefRefreshToken);
    await prefs.remove(_prefUserId);
    await prefs.remove(_prefUserEmail);
    await prefs.remove(_prefUserDisplayName);
  }

  Future<ApiUser> register({
    required String loginOrEmail,
    required String password,
    required String displayName,
  }) async {
    final email = normalizeEmail(loginOrEmail);
    final url = Uri.parse('$baseUrl/auth/register');

    final response = await _wrapRequest(() => http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
        'display_name': displayName.trim().isEmpty ? 'Пользователь' : displayName.trim(),
      }),
    ));

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return login(loginOrEmail: loginOrEmail, password: password);
    } else {
      throw _parseError(response);
    }
  }

  Future<ApiUser> login({
    required String loginOrEmail,
    required String password,
  }) async {
    final email = normalizeEmail(loginOrEmail);
    final url = Uri.parse('$baseUrl/auth/login');

    final response = await _wrapRequest(() => http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
      }),
    ));

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final user = ApiUser.fromJson(data['user'] as Map<String, dynamic>);
      await _saveTokens(
        accessToken: data['access_token']?.toString() ?? '',
        refreshToken: data['refresh_token']?.toString() ?? '',
        user: user,
      );
      return user;
    } else {
      throw _parseError(response);
    }
  }

  Future<bool>? _refreshFuture;

  Future<bool> refreshToken() async {
    if (_refreshToken == null || _refreshToken!.isEmpty) return false;
    if (_refreshFuture != null) {
      return await _refreshFuture!;
    }

    _refreshFuture = _doRefreshToken();
    try {
      return await _refreshFuture!;
    } finally {
      _refreshFuture = null;
    }
  }

  Future<bool> _doRefreshToken() async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/refresh'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'refresh_token': _refreshToken}),
      );
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        _accessToken = data['access_token']?.toString();
        _refreshToken = data['refresh_token']?.toString();
        final prefs = await SharedPreferences.getInstance();
        if (_accessToken != null) await prefs.setString(_prefAccessToken, _accessToken!);
        if (_refreshToken != null) await prefs.setString(_prefRefreshToken, _refreshToken!);
        return true;
      }
    } catch (_) {}
    return false;
  }

  Future<http.Response> _authorizedRequest(
    String method,
    String endpoint, {
    Map<String, dynamic>? body,
    Map<String, dynamic>? queryParams,
  }) async {
    Uri uri = Uri.parse('$baseUrl$endpoint');
    if (queryParams != null && queryParams.isNotEmpty) {
      uri = uri.replace(queryParameters: queryParams);
    }

    final headers = {
      'Content-Type': 'application/json',
      if (_accessToken != null) 'Authorization': 'Bearer $_accessToken',
    };

    http.Response response = await _wrapRequest(() {
      switch (method.toUpperCase()) {
        case 'GET':
          return http.get(uri, headers: headers);
        case 'POST':
          return http.post(uri, headers: headers, body: body != null ? jsonEncode(body) : null);
        case 'PATCH':
          return http.patch(uri, headers: headers, body: body != null ? jsonEncode(body) : null);
        case 'DELETE':
          return http.delete(uri, headers: headers, body: body != null ? jsonEncode(body) : null);
        default:
          throw ApiException('Неподдерживаемый HTTP метод $method');
      }
    });

    if (response.statusCode == 401 && _refreshToken != null) {
      final refreshed = await refreshToken();
      if (refreshed) {
        headers['Authorization'] = 'Bearer $_accessToken';
        switch (method.toUpperCase()) {
          case 'GET':
            return await http.get(uri, headers: headers);
          case 'POST':
            return await http.post(uri, headers: headers, body: body != null ? jsonEncode(body) : null);
          case 'PATCH':
            return await http.patch(uri, headers: headers, body: body != null ? jsonEncode(body) : null);
          case 'DELETE':
            return await http.delete(uri, headers: headers, body: body != null ? jsonEncode(body) : null);
        }
      }
    }

    return response;
  }

  Future<List<ApiShoppingList>> getLists({String? query, bool? owned}) async {
    final params = <String, String>{};
    if (query != null && query.trim().isNotEmpty) params['q'] = query.trim();
    if (owned != null) params['owned'] = owned.toString();

    final response = await _authorizedRequest('GET', '/lists', queryParams: params);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final rawItems = data['items'] as List<dynamic>? ?? [];
      return rawItems
          .whereType<Map<String, dynamic>>()
          .map(ApiShoppingList.fromJson)
          .toList();
    }
    throw _parseError(response);
  }

  Future<ApiShoppingList> createList(String name, {String? description, List<String>? items}) async {
    final body = <String, dynamic>{'name': name.trim()};
    if (description != null) body['description'] = description.trim();
    if (items != null) body['items'] = items;
    final response = await _authorizedRequest('POST', '/lists', body: body);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiShoppingList.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<Map<String, dynamic>> getListDetail(String listId) async {
    final response = await _authorizedRequest('GET', '/lists/$listId');
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final list = ApiShoppingList.fromJson(data);
      final rawItems = data['items'] as List<dynamic>? ?? [];
      final items = rawItems
          .whereType<Map<String, dynamic>>()
          .map(ApiShoppingItem.fromJson)
          .toList();
      return {'list': list, 'items': items};
    }
    throw _parseError(response);
  }

  Future<ApiShoppingList> updateList(String listId, {String? name, String? description}) async {
    final body = <String, dynamic>{};
    if (name != null) body['name'] = name.trim();
    if (description != null) body['description'] = description.trim();
    final response = await _authorizedRequest('PATCH', '/lists/$listId', body: body);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiShoppingList.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<void> deleteList(String listId) async {
    final response = await _authorizedRequest('DELETE', '/lists/$listId');
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw _parseError(response);
  }

  Future<ApiAddResult> addItem(
    String listId,
    String name, {
    double quantity = 1.0,
    String? unit,
    int priority = 1,
  }) async {
    final response = await _authorizedRequest(
      'POST',
      '/lists/$listId/items',
      queryParams: {'suggest': 'true'},
      body: {
        'name': name.trim(),
        'quantity': quantity,
        if (unit != null && unit.isNotEmpty) 'unit': unit,
        'priority': priority,
      },
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final item = ApiShoppingItem.fromJson(data['item'] as Map<String, dynamic>);
      final rawSuggestions = data['suggestions'] as List<dynamic>? ?? [];
      final suggestions = rawSuggestions
          .whereType<Map<String, dynamic>>()
          .map(ApiItemSuggestion.fromJson)
          .toList();
      return ApiAddResult(item: item, suggestions: suggestions);
    }
    throw _parseError(response);
  }

  Future<ApiShoppingItem> updateItem(
    String listId,
    String itemId, {
    bool? checked,
    String? name,
    double? quantity,
    String? unit,
  }) async {
    final body = <String, dynamic>{};
    if (checked != null) body['checked'] = checked;
    if (name != null) body['name'] = name.trim();
    if (quantity != null) body['quantity'] = quantity;
    if (unit != null) {
      final trimmed = unit.trim();
      if (trimmed.isNotEmpty) body['unit'] = trimmed;
    }

    final response = await _authorizedRequest(
      'PATCH',
      '/lists/$listId/items/$itemId',
      body: body,
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiShoppingItem.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<void> deleteItem(String listId, String itemId) async {
    final response = await _authorizedRequest('DELETE', '/lists/$listId/items/$itemId');
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw _parseError(response);
  }

  Future<List<ApiCatalogProduct>> searchCatalog(String query) async {
    if (query.trim().isEmpty) return [];
    final response = await _authorizedRequest(
      'GET',
      '/products/search',
      queryParams: {'q': query.trim(), 'limit': '15'},
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final rawItems = data['items'] as List<dynamic>? ?? [];
      return rawItems
          .whereType<Map<String, dynamic>>()
          .map(ApiCatalogProduct.fromJson)
          .toList();
    }
    return [];
  }

  Future<List<ApiCatalogProduct>> getProducts({
    int limit = 20,
    int offset = 0,
    String? categoryId,
  }) async {
    final params = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
      if (categoryId != null && categoryId.isNotEmpty) 'category_id': categoryId,
    };
    final response = await _authorizedRequest('GET', '/products', queryParams: params);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final rawItems = data['items'] as List<dynamic>? ?? [];
      return rawItems
          .whereType<Map<String, dynamic>>()
          .map(ApiCatalogProduct.fromJson)
          .toList();
    }
    return [];
  }

  Future<ApiInviteInfo> createInvite(
    String listId, {
    String mode = 'share',
    String role = 'editor',
  }) async {
    final response = await _authorizedRequest(
      'POST',
      '/lists/$listId/share',
      body: {'mode': mode, 'role': role},
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiInviteInfo.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<ApiShoppingList> joinList(String code) async {
    final cleanCode = code.trim().toUpperCase();
    final response = await _authorizedRequest(
      'POST',
      '/lists/join',
      body: {'code': cleanCode},
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final listId = data['list_id']?.toString() ?? '';
      if (listId.isNotEmpty) {
        final detail = await getListDetail(listId);
        return detail['list'] as ApiShoppingList;
      }
      return ApiShoppingList(
        id: listId,
        name: 'Новый список',
        isOwner: false,
        isShared: true,
        isSystem: false,
        role: data['role']?.toString() ?? 'editor',
        itemCount: 0,
        checkedCount: 0,
        createdAt: DateTime.now(),
      );
    }
    throw _parseError(response);
  }

  Future<List<ApiReplenishItem>> getReplenish() async {
    final response = await _authorizedRequest('GET', '/smart/replenish');
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      final rawItems = data['items'] as List<dynamic>? ?? [];
      return rawItems
          .whereType<Map<String, dynamic>>()
          .map(ApiReplenishItem.fromJson)
          .toList();
    }
    throw _parseError(response);
  }

  Future<ApiUserSettings> getUserSettings() async {
    final response = await _authorizedRequest('GET', '/me/settings');
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiUserSettings.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<ApiUserSettings> updateUserSettings({
    bool? aiSuggestionsEnabled,
    int? suggestionsLimit,
  }) async {
    final body = <String, dynamic>{};
    if (aiSuggestionsEnabled != null) body['ai_suggestions_enabled'] = aiSuggestionsEnabled;
    if (suggestionsLimit != null) body['suggestions_limit'] = suggestionsLimit;

    final response = await _authorizedRequest(
      'PATCH',
      '/me/settings',
      body: body,
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiUserSettings.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<List<ApiCategory>> getCategories() async {
    try {
      final response = await _authorizedRequest('GET', '/products/categories');
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        final rawItems = data['items'] as List<dynamic>? ?? [];
        return rawItems
            .whereType<Map<String, dynamic>>()
            .map(ApiCategory.fromJson)
            .toList();
      }
    } catch (_) {}
    return [];
  }

  Future<ApiParsedItem> parseItem(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return ApiParsedItem(name: '', quantity: 1.0);
    try {
      final response = await _authorizedRequest(
        'POST',
        '/smart/parse',
        body: {'text': trimmed},
      );
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        return ApiParsedItem.fromJson(data);
      }
    } catch (_) {}
    return ApiParsedItem(name: trimmed, quantity: 1.0);
  }

  Future<List<ApiItemSuggestion>> getListSuggestions(String listId, {int limit = 6}) async {
    try {
      final response = await _authorizedRequest(
        'GET',
        '/lists/$listId/suggestions',
        queryParams: {'limit': limit.toString()},
      );
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        final rawItems = data['items'] as List<dynamic>? ?? [];
        return rawItems
            .whereType<Map<String, dynamic>>()
            .map(ApiItemSuggestion.fromJson)
            .toList();
      }
    } catch (_) {}
    return [];
  }

  Future<List<ApiItemSuggestion>> getItemsSuggestions(List<String> items, {int limit = 6}) async {
    final clean = items.map((e) => e.trim()).where((e) => e.isNotEmpty).take(15).toList();
    if (clean.isEmpty) return [];
    try {
      final response = await _authorizedRequest(
        'GET',
        '/suggestions',
        queryParams: {
          'item': clean,
          'limit': limit.toString(),
        },
      );
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        final rawItems = data['items'] as List<dynamic>? ?? [];
        return rawItems
            .whereType<Map<String, dynamic>>()
            .map(ApiItemSuggestion.fromJson)
            .toList();
      }
    } catch (_) {}
    return [];
  }

  String get _historyKey =>
      'search_history_${_currentUser?.id ?? 'guest'}';

  Future<List<String>> getSearchHistory() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getStringList(_historyKey) ?? [];
  }

  Future<void> addSearchQuery(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return;
    final prefs = await SharedPreferences.getInstance();
    final history = prefs.getStringList(_historyKey) ?? [];
    history.removeWhere((e) => e.toLowerCase() == trimmed.toLowerCase());
    history.insert(0, trimmed);
    if (history.length > 20) {
      history.removeRange(20, history.length);
    }
    await prefs.setStringList(_historyKey, history);
  }

  Future<void> removeSearchQuery(String query) async {
    final prefs = await SharedPreferences.getInstance();
    final history = prefs.getStringList(_historyKey) ?? [];
    history.removeWhere((e) => e.toLowerCase() == query.trim().toLowerCase());
    await prefs.setStringList(_historyKey, history);
  }

  Future<void> clearSearchHistory() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_historyKey);
  }

  Future<int> clearItems(String listId, {bool checkedOnly = false}) async {
    final response = await _authorizedRequest(
      'DELETE',
      '/lists/$listId/items',
      queryParams: {'checked_only': checkedOnly.toString()},
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return parseApiInt(data['deleted']);
    }
    throw _parseError(response);
  }

  Future<ApiShoppingList> getFavoritesList() async {
    final response = await _authorizedRequest('GET', '/lists/favorites');
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiShoppingList.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<ApiUserProfile> getMe() async {
    final response = await _authorizedRequest('GET', '/me');
    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      return ApiUserProfile.fromJson(data);
    }
    throw _parseError(response);
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    final response = await _authorizedRequest(
      'POST',
      '/auth/change-password',
      body: {
        'current_password': currentPassword,
        'new_password': newPassword,
      },
    );
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw _parseError(response);
  }

  Future<List<ApiUserSession>> getSessions() async {
    try {
      final response = await _authorizedRequest('GET', '/auth/sessions');
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final data = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        final rawItems = data['items'] as List<dynamic>? ?? [];
        return rawItems
            .whereType<Map<String, dynamic>>()
            .map(ApiUserSession.fromJson)
            .toList();
      }
    } catch (_) {}
    return [];
  }

  ApiException _parseError(http.Response response) {
    String? serverMessage;
    try {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (data is Map<String, dynamic>) {
        if (response.statusCode == 422) {
          final err = data['error'];
          if (err is Map<String, dynamic>) {
            final details = err['details'];
            if (details is Map<String, dynamic> && details['fields'] is List) {
              final fields = details['fields'] as List;
              final hasPassword = fields.any((f) => f is Map && f['field'] == 'password');
              final hasEmail = fields.any((f) => f is Map && f['field'] == 'email');
              if (hasPassword && hasEmail) {
                return ApiException('Неправильный логин или что-то не так с паролем (минимум 8 символов)', statusCode: 422);
              } else if (hasPassword) {
                return ApiException('Что-то не так с паролем (должен быть не менее 8 символов)', statusCode: 422);
              } else if (hasEmail) {
                return ApiException('Неправильный логин (используйте латинские буквы и цифры)', statusCode: 422);
              }

              for (final f in fields) {
                if (f is Map) {
                  final issue = f['issue']?.toString();
                  if (issue != null && issue.isNotEmpty) {
                    return ApiException(issue, statusCode: 422);
                  }
                }
              }
            }
            final msg = err['message']?.toString();
            if (msg != null && msg.isNotEmpty && !msg.toLowerCase().contains('unprocessable')) {
              return ApiException(msg, statusCode: 422);
            }
          }
          return ApiException('Неправильный формат данных или некорректные поля', statusCode: 422);
        }

        if (data.containsKey('error') && data['error'] is Map<String, dynamic>) {
          final err = data['error'] as Map<String, dynamic>;
          final msg = err['message']?.toString();
          if (msg != null && msg.isNotEmpty) {
            serverMessage = msg;
          }
        } else if (data.containsKey('message')) {
          serverMessage = data['message']?.toString();
        } else if (data.containsKey('detail')) {
          final detail = data['detail'];
          if (detail is String) serverMessage = detail;
        }
      }
    } catch (_) {}

    if (serverMessage != null && serverMessage.isNotEmpty) {
      return ApiException(serverMessage, statusCode: response.statusCode);
    }

    if (response.statusCode == 401) {
      return ApiException('Сессия истекла или требуется повторный вход', statusCode: 401);
    }
    if (response.statusCode == 403) {
      return ApiException('Недостаточно прав для выполнения действия', statusCode: 403);
    }
    if (response.statusCode == 404) {
      return ApiException('Запрашиваемый ресурс или список не найден', statusCode: 404);
    }
    if (response.statusCode == 409) {
      return ApiException('Конфликт данных или превышен лимит', statusCode: 409);
    }
    if (response.statusCode == 429) {
      return ApiException('Слишком много запросов. Подождите минуту.', statusCode: 429);
    }
    if (response.statusCode == 422) {
      return ApiException('Неправильный формат запроса или некорректные данные', statusCode: 422);
    }

    return ApiException(
      'Не удалось выполнить запрос (код ${response.statusCode}).',
      statusCode: response.statusCode,
    );
  }
}
