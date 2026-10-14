// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';
import 'package:project_android/main.dart';
import 'package:project_android/services/api_service.dart';

void main() {
  test('parseApiDouble handles both num, string, and null safely', () {
    expect(parseApiDouble(2), 2.0);
    expect(parseApiDouble(2.5), 2.5);
    expect(parseApiDouble('2'), 2.0);
    expect(parseApiDouble('3.14'), 3.14);
    expect(parseApiDouble(null, 1.0), 1.0);
    expect(parseApiDouble('invalid', 1.0), 1.0);
  });

  test('parseApiInt handles both num, string, and null safely', () {
    expect(parseApiInt(42), 42);
    expect(parseApiInt('42'), 42);
    expect(parseApiInt(null, 0), 0);
    expect(parseApiInt('invalid', 5), 5);
  });

  testWidgets('App smoke test builds without error', (WidgetTester tester) async {
    await tester.pumpWidget(const MyApp());
    expect(find.byType(MyApp), findsOneWidget);
  });
}
