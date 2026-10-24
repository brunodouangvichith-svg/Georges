import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:george_mobile/features/univers/widgets/univers_radar.dart';
import 'package:george_mobile/features/univers/widgets/univers_radar_layout.dart';
import 'package:george_mobile/models/security.dart';

void main() {
  testWidgets('tapping a tick selects it, even inside the zoomable viewer', (tester) async {
    final layout = buildRadarLayout(
      [for (var i = 0; i < 4; i++) Security(symbol: 'S$i', name: 'S$i', country: 'FR', currency: 'EUR', sector: 'Tech')],
      const {},
      const {},
    );
    String? selected;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Align(
            alignment: Alignment.topLeft,
            child: SizedBox(
              width: 380,
              child: UniversRadar(layout: layout, selectedSymbol: null, onSelect: (s) => selected = s),
            ),
          ),
        ),
      ),
    );
    // Pas de bouton de réinitialisation tant qu'on n'a pas zoomé.
    expect(find.text('Réinitialiser le zoom'), findsNothing);

    // Graduation de S1, sur l'anneau : centre (380, 340) du repère web, mis à
    // l'échelle 380 / 760 = 0,5.
    final item = layout.items[1];
    const k = 0.5;
    final origin = tester.getTopLeft(find.byType(UniversRadar));
    await tester.tapAt(origin +
        Offset((380 + math.cos(item.angle) * rTickIn) * k, (340 + math.sin(item.angle) * rTickIn) * k));
    await tester.pump();
    expect(selected, 'S1');
  });
}
