import 'package:flutter/material.dart';

/// Dialogue de réponse partagé — miroir de web/src/components/ResponsePopup.jsx
/// (états loading/done/error, `loadingText` paramétrable par appel). Réutilisé
/// pour toute action qui appelle le backend et affiche un texte en retour :
/// explication de décision, chat, rafraîchissement des prix, collecte macro.
Future<void> showResponseDialog(
  BuildContext context, {
  required String title,
  required String loadingText,
  required Future<String> Function() action,
}) {
  return showDialog(
    context: context,
    builder: (context) => _ResponseDialog(title: title, loadingText: loadingText, action: action),
  );
}

class _ResponseDialog extends StatefulWidget {
  const _ResponseDialog({required this.title, required this.loadingText, required this.action});

  final String title;
  final String loadingText;
  final Future<String> Function() action;

  @override
  State<_ResponseDialog> createState() => _ResponseDialogState();
}

class _ResponseDialogState extends State<_ResponseDialog> {
  String? _text;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    widget.action().then((text) {
      if (!mounted) return;
      setState(() {
        _text = text;
        _loading = false;
      });
    }).catchError((Object e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 400),
        child: SingleChildScrollView(
          child: _loading
              ? Row(
                  children: [
                    const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
                    const SizedBox(width: 12),
                    Expanded(child: Text(widget.loadingText)),
                  ],
                )
              : Text(
                  _error ?? _text ?? '',
                  style: _error != null ? TextStyle(color: Theme.of(context).colorScheme.error) : null,
                ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Fermer')),
      ],
    );
  }
}
