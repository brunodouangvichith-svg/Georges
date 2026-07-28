import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/agents_repository.dart';

/// Résumé compact de l'activité des sous-agents — miroir de la section
/// "Sous-agents — activité récente" de web/src/views/Univers.jsx, condensée
/// en une carte plutôt qu'une liste complète (espace mobile restreint).
class AgentActivityCard extends ConsumerWidget {
  const AgentActivityCard({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activityAsync = ref.watch(agentActivityProvider);

    return Container(
      width: 220,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(10)),
      child: activityAsync.when(
        loading: () => const Center(child: CircularProgressIndicator(strokeWidth: 2)),
        error: (e, st) => Text('Activité indisponible', style: Theme.of(context).textTheme.bodySmall),
        data: (page) {
          if (page.items.isEmpty) {
            return Text(
              'Aucun événement — les sous-agents de veille arrivent en Phase 7.',
              style: Theme.of(context).textTheme.labelSmall,
            );
          }
          final latest = page.items.first;
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Sous-agents — activité récente', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 4),
              Row(
                children: [
                  Icon(Icons.circle,
                      size: 8,
                      color: latest.status == 'validated'
                          ? Colors.green.shade400
                          : latest.status == 'pending'
                              ? Colors.amber.shade600
                              : Colors.red.shade400),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      '${latest.agentName} · ${latest.description}',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ],
          );
        },
      ),
    );
  }
}
