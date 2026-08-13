import 'package:flutter_test/flutter_test.dart';
import 'package:george_mobile/core/indicators/technical_indicators.dart';
import 'package:george_mobile/models/price_bar.dart';

/// Port Dart de tests/test_patterns.py:ramp / tests/test_features.py --
/// même construction (rampe linéaire, open = clôture précédente, high/low à
/// ±0.2%) pour que ces tests suivent les mêmes attentes directionnelles que
/// leurs équivalents backend (engine/patterns/common.py).
List<PriceBar> _ramp(double start, double end, int n) {
  final closes = List.generate(n, (i) => start + (end - start) * i / (n - 1));
  final bars = <PriceBar>[];
  var prevClose = closes[0];
  for (var i = 0; i < n; i++) {
    final close = closes[i];
    final open = i == 0 ? close : prevClose;
    final high = (open > close ? open : close) * 1.002;
    final low = (open < close ? open : close) * 0.998;
    bars.add(PriceBar(
      ts: DateTime(2023, 1, 2).add(Duration(days: i)),
      open: open,
      high: high,
      low: low,
      close: close,
      volume: 1000000,
    ));
    prevClose = close;
  }
  return bars;
}

void main() {
  group('ema', () {
    test('is null before the window warms up', () {
      final closes = _ramp(100, 110, 10).map((c) => c.close).toList();
      final result = ema(closes, 14);
      expect(result[5], isNull);
    });

    test('converges to a constant series', () {
      final closes = List<double>.filled(30, 100.0);
      final result = ema(closes, 12);
      expect(result.last, closeTo(100.0, 0.001));
    });
  });

  group('macd', () {
    test('is null before the slow span warms up', () {
      final closes = _ramp(100, 110, 10).map((c) => c.close).toList();
      final result = macd(closes);
      expect(result.macdLine[5], isNull);
      expect(result.histogram[5], isNull);
    });

    test('is positive on an uninterrupted rally', () {
      final closes = _ramp(100, 160, 60).map((c) => c.close).toList();
      final result = macd(closes);
      expect(result.macdLine.last, isNotNull);
      expect(result.macdLine.last, greaterThan(0));
    });
  });

  group('bollingerBands', () {
    test('is null before the window warms up', () {
      final closes = _ramp(100, 110, 10).map((c) => c.close).toList();
      final result = bollingerBands(closes);
      expect(result.mid[5], isNull);
    });

    test('bands are ordered around the median on a volatile series', () {
      final closes = _ramp(100, 130, 30).map((c) => c.close).toList();
      final result = bollingerBands(closes);
      final i = closes.length - 1;
      expect(result.lower[i], lessThan(result.mid[i]!));
      expect(result.mid[i], lessThan(result.upper[i]!));
    });
  });

  group('stochasticOscillator', () {
    test('is null before the window warms up', () {
      final candles = _ramp(100, 110, 10);
      final result = stochasticOscillator(candles);
      expect(result.percentK[5], isNull);
    });

    test('is high on an uninterrupted rally (close near the window high)', () {
      final candles = _ramp(100, 130, 30);
      final result = stochasticOscillator(candles);
      expect(result.percentK.last, isNotNull);
      expect(result.percentK.last, greaterThan(90.0));
    });

    test('is low on an uninterrupted selloff (close near the window low)', () {
      final candles = _ramp(130, 100, 30);
      final result = stochasticOscillator(candles);
      expect(result.percentK.last, isNotNull);
      expect(result.percentK.last, lessThan(10.0));
    });
  });
}
