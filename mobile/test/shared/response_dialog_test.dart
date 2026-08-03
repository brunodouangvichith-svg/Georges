import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:george_mobile/data/share_repository.dart';
import 'package:george_mobile/shared/widgets/response_dialog.dart';

Widget _harness() {
  return ProviderScope(
    child: MaterialApp(
      home: Scaffold(body: Builder(builder: (context) => ElevatedButton(onPressed: () {}, child: const Text('Ouvrir')))),
    ),
  );
}

void main() {
  testWidgets('copy/share icons are hidden while loading, shown once text arrives', (tester) async {
    late BuildContext capturedContext;
    await tester.pumpWidget(_harness());
    capturedContext = tester.element(find.text('Ouvrir'));

    showResponseDialog(
      capturedContext,
      title: 'George explique',
      loadingText: 'Chargement…',
      action: () async {
        await Future<void>.delayed(const Duration(milliseconds: 50));
        return 'Explication réelle.';
      },
    );
    await tester.pump();

    expect(find.text('📋'), findsNothing);
    expect(find.text('📤'), findsNothing);

    await tester.pump(const Duration(milliseconds: 60));
    await tester.pumpAndSettle();

    expect(find.text('📋'), findsOneWidget);
    expect(find.text('📤'), findsOneWidget);
  });

  testWidgets('tapping copy puts the text on the clipboard', (tester) async {
    String? clipboardText;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') {
        clipboardText = (call.arguments as Map)['text'] as String;
      }
      return null;
    });

    late BuildContext capturedContext;
    await tester.pumpWidget(_harness());
    capturedContext = tester.element(find.text('Ouvrir'));

    showResponseDialog(
      capturedContext,
      title: 'George explique',
      loadingText: 'Chargement…',
      action: () async => 'Explication réelle.',
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('📋'));
    await tester.pump();

    expect(clipboardText, 'Explication réelle.');
  });

  testWidgets('sharing by email calls ShareRepository with the symbol when provided', (tester) async {
    String? capturedSymbol;
    String? capturedText;

    await tester.pumpWidget(ProviderScope(
      overrides: [
        shareRepositoryProvider.overrideWithValue(_FakeShareRepository((toEmail, subject, text, symbol) {
          capturedSymbol = symbol;
          capturedText = text;
        })),
      ],
      child: MaterialApp(
        home: Scaffold(body: Builder(builder: (context) => ElevatedButton(onPressed: () {}, child: const Text('Ouvrir')))),
      ),
    ));
    final capturedContext = tester.element(find.text('Ouvrir'));

    showResponseDialog(
      capturedContext,
      title: 'George explique — ABVX.PA',
      loadingText: 'Chargement…',
      action: () async => 'Double Bottom détecté.',
      symbol: 'ABVX.PA',
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('📤'));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField), 'investisseur@example.com');
    await tester.tap(find.text('✅ Envoyer'));
    await tester.pumpAndSettle();

    expect(capturedSymbol, 'ABVX.PA');
    expect(capturedText, 'Double Bottom détecté.');
  });
}

class _FakeShareRepository implements ShareRepository {
  _FakeShareRepository(this.onShare);

  final void Function(String toEmail, String subject, String text, String? symbol) onShare;

  @override
  Future<ShareEmailResult> shareByEmail({
    required String toEmail,
    required String subject,
    required String text,
    String? symbol,
    double? takeProfit,
    double? stopLoss,
  }) async {
    onShare(toEmail, subject, text, symbol);
    return ShareEmailResult(sent: true, chartAttached: symbol != null);
  }
}
