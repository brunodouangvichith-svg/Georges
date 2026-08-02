import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme/app_theme.dart';
import '../../../data/baskets_repository.dart';

Color _scoreColor(double score) {
  if (score >= 75) return AppColors.positive;
  if (score >= 65) return AppColors.warning;
  return AppColors.negative;
}

/// Miroir de web/src/views/Paniers.jsx:BasketIndexRow — score + barre de
/// progression + performances 1j/1s/1m pour un panier.
class BasketIndexCard extends ConsumerWidget {
  const BasketIndexCard({super.key, required this.basketId, required this.basketName});

  final int basketId;
  final String basketName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final indexAsync = ref.watch(georgeIndexProvider(basketId));

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: indexAsync.when(
        loading: () => Text('$basketName — …'),
        error: (e, st) => Text('$basketName — indisponible'),
        data: (index) {
          final score = index.georgeIndex;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(basketName, style: Theme.of(context).textTheme.bodySmall),
                  Text(
                    score != null ? score.round().toString() : '—',
                    style: monoTextStyle(
                      fontWeight: FontWeight.bold,
                      color: score != null ? _scoreColor(score) : Theme.of(context).colorScheme.outline,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: (score ?? 0) / 100,
                  minHeight: 5,
                  backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
                  color: score != null ? _scoreColor(score) : Theme.of(context).colorScheme.outline,
                ),
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  _PerformanceBadge('1j', index.performance1j),
                  const SizedBox(width: 10),
                  _PerformanceBadge('1s', index.performance1s),
                  const SizedBox(width: 10),
                  _PerformanceBadge('1m', index.performance1m),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}

class _PerformanceBadge extends StatelessWidget {
  const _PerformanceBadge(this.label, this.value);

  final String label;
  final double? value;

  @override
  Widget build(BuildContext context) {
    final v = value;
    final color = v == null
        ? Theme.of(context).colorScheme.outline
        : v >= 0
            ? AppColors.positive
            : AppColors.negative;
    final text = v == null ? '—' : '${v >= 0 ? '+' : ''}${v.toStringAsFixed(1)}%';
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('$label ', style: Theme.of(context).textTheme.labelSmall),
        Text(text, style: monoTextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 11)),
      ],
    );
  }
}
