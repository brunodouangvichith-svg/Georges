import 'package:flutter/material.dart';

class _MacroPoint {
  final String name;
  final String value;
  final bool up;

  const _MacroPoint(this.name, this.value, this.up);
}

// Miroir exact de web/src/data.js:macro — donnée explicitement FICTIVE
// (aucune table taux/indices/devises n'existe encore dans le schéma), à ne
// jamais présenter comme réelle. Ne pas retirer la mention "fictif".
const _macro = [
  _MacroPoint('Brent (USD)', '84.2', true),
  _MacroPoint('EUR/USD', '1.072', false),
  _MacroPoint('OAT 10 ans', '3.14%', true),
  _MacroPoint('CAC 40', '7 940', true),
];

class MacroTile extends StatelessWidget {
  const MacroTile({super.key});

  void _showDetail(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Repères macro (donnée fictive)'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final m in _macro)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(m.name),
                    Text(
                      '${m.up ? '▲' : '▼'} ${m.value}',
                      style: TextStyle(
                        color: m.up ? Colors.green.shade400 : Colors.red.shade400,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(dialogContext).pop(), child: const Text('Fermer')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: () => _showDetail(context),
      child: Container(
        width: 170,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(border: Border.all(color: Theme.of(context).dividerColor), borderRadius: BorderRadius.circular(10)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Repères macro (donnée fictive)',
                style: Theme.of(context).textTheme.labelSmall, maxLines: 2),
            const SizedBox(height: 4),
            for (final m in _macro)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        m.name,
                        style: Theme.of(context).textTheme.bodySmall,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '${m.up ? '▲' : '▼'} ${m.value}',
                      style: TextStyle(
                        color: m.up ? Colors.green.shade400 : Colors.red.shade400,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
