import 'dart:math' as math;

import '../../../models/decision.dart';
import '../../../models/pattern.dart';
import '../../../models/security.dart';

/// Géométrie du radar de l'écran Univers — port de
/// `web/src/components/universRadarLayout.js`, mêmes règles : une graduation
/// par valeur, regroupées par secteur (le plus gros d'abord) avec un petit
/// espace entre secteurs, étiquette de secteur à partir de 4 valeurs.
///
/// Les rayons sont exprimés dans le repère du web (viewBox de 760 de large)
/// et mis à l'échelle par le painter : `scale = largeur / 760`.
const double radarViewWidth = 760;
const double radarScale = 0.9; // même réduction de 10 % que le web
const double rIn = 250 * radarScale;
const double rTickIn = 256 * radarScale;
const double rTickOut = 264 * radarScale;
const double rBar = 270 * radarScale;
const double barScale = 0.5 * radarScale;
const double rSectorLabel = 236 * radarScale;
const int _sectorGap = 2;
const int _minSectorLabel = 4;

/// Décisions haussières / neutres, comme `web/src/data.js`.
bool isBullishDecision(String? type) => type == 'Achat' || type == 'Renforcer';

class RadarItem {
  const RadarItem({
    required this.symbol,
    required this.name,
    required this.angle,
    required this.confidence,
    required this.decision,
  });

  final String symbol;
  final String name;

  /// Radians, 0 = 3 h, sens horaire (repère écran), départ à -π/2 (12 h).
  final double angle;

  /// 0-100, `null` = aucune figure détectée.
  final double? confidence;
  final String? decision;
}

class RadarSectorLabel {
  const RadarSectorLabel({required this.sector, required this.text, required this.angle});

  final String sector;
  final String text;
  final double angle;
}

class RadarLayout {
  const RadarLayout({required this.items, required this.labels, required this.step});

  final List<RadarItem> items;
  final List<RadarSectorLabel> labels;

  /// Écart angulaire entre deux graduations voisines.
  final double step;

  /// Valeur la plus proche d'un angle (radians), si elle est à moins d'une
  /// graduation et demie — sert au tap sur le radar.
  RadarItem? nearest(double angle) {
    RadarItem? best;
    var bestDiff = double.infinity;
    for (final item in items) {
      var diff = (item.angle - angle) % (2 * math.pi);
      if (diff > math.pi) diff = 2 * math.pi - diff;
      if (diff < 0) diff = -diff;
      if (diff < bestDiff) {
        bestDiff = diff;
        best = item;
      }
    }
    return bestDiff <= step * 1.5 ? best : null;
  }
}

String _truncate(String s, int n) => s.length > n ? '${s.substring(0, n - 1)}…' : s;

RadarLayout buildRadarLayout(
  List<Security> securities,
  Map<String, Pattern> patternsBySymbol,
  Map<String, Decision> decisionsBySymbol,
) {
  final groups = <String, List<Security>>{};
  for (final s in securities) {
    final key = s.sector.isEmpty ? 'Autre' : s.sector;
    groups.putIfAbsent(key, () => []).add(s);
  }
  // Tri stable : plus gros secteur d'abord, ordre d'apparition sinon (comme
  // le `sort` du web, stable en JS moderne).
  final sectors = groups.entries.toList();
  final order = {for (var i = 0; i < sectors.length; i++) sectors[i].key: i};
  sectors.sort((a, b) {
    final bySize = b.value.length.compareTo(a.value.length);
    return bySize != 0 ? bySize : order[a.key]!.compareTo(order[b.key]!);
  });

  final slots = securities.length + sectors.length * _sectorGap;
  final step = slots > 0 ? (math.pi * 2) / slots : 0.0;
  final items = <RadarItem>[];
  final labels = <RadarSectorLabel>[];
  var slot = 0;
  for (final entry in sectors) {
    final start = slot;
    for (final s in entry.value) {
      final pattern = patternsBySymbol[s.symbol];
      items.add(RadarItem(
        symbol: s.symbol,
        name: s.name,
        angle: -math.pi / 2 + slot * step,
        confidence: pattern?.confidence.clamp(0, 100).toDouble(),
        decision: decisionsBySymbol[s.symbol]?.decisionType,
      ));
      slot++;
    }
    if (entry.value.length >= _minSectorLabel) {
      labels.add(RadarSectorLabel(
        sector: entry.key,
        text: _truncate(entry.key.toUpperCase(), 16),
        angle: -math.pi / 2 + (start + (entry.value.length - 1) / 2) * step,
      ));
    }
    slot += _sectorGap;
  }
  return RadarLayout(items: items, labels: labels, step: step);
}
