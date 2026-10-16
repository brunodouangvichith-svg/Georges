/// Port Dart de web/src/components/markdownBlocks.js : découpe minimale du
/// Markdown du rapport stratégique (titres, puces, listes numérotées,
/// paragraphes, **gras**, renvois [n]). Le texte vient d'un LLM : il est
/// toujours rendu comme du texte.
class MdBlock {
  const MdBlock(this.type, {this.text = '', this.items = const []});

  /// 'h2' | 'h3' | 'p' | 'ul' | 'ol'
  final String type;
  final String text;
  final List<String> items;
}

class MdSegment {
  const MdSegment(this.type, {this.text = '', this.ref});

  /// 'text' | 'bold' | 'ref'
  final String type;
  final String text;
  final int? ref;
}

final _heading = RegExp(r'^(#{1,4})\s+(.*)$');
final _bullet = RegExp(r'^[-*•]\s+(.*)$');
final _numbered = RegExp(r'^\d+[.)]\s+(.*)$');
final _inline = RegExp(r'\*\*(.+?)\*\*|\[(\d{1,3})\]');

List<MdBlock> parseMarkdownBlocks(String? markdown) {
  final blocks = <MdBlock>[];
  var paragraph = <String>[];
  String? listType;
  var listItems = <String>[];

  void flushParagraph() {
    if (paragraph.isNotEmpty) blocks.add(MdBlock('p', text: paragraph.join(' ')));
    paragraph = [];
  }

  void flushList() {
    if (listType != null) blocks.add(MdBlock(listType!, items: listItems));
    listType = null;
    listItems = [];
  }

  for (final raw in (markdown ?? '').split('\n')) {
    final line = raw.trim();
    if (line.isEmpty) {
      flushParagraph();
      flushList();
      continue;
    }
    final heading = _heading.firstMatch(line);
    if (heading != null) {
      flushParagraph();
      flushList();
      blocks.add(MdBlock(heading.group(1)!.length <= 2 ? 'h2' : 'h3', text: heading.group(2)!));
      continue;
    }
    final bullet = _bullet.firstMatch(line);
    final numbered = _numbered.firstMatch(line);
    if (bullet != null || numbered != null) {
      flushParagraph();
      final type = bullet != null ? 'ul' : 'ol';
      if (listType != type) {
        flushList();
        listType = type;
      }
      listItems.add((bullet ?? numbered)!.group(1)!);
      continue;
    }
    flushList();
    paragraph.add(line);
  }
  flushParagraph();
  flushList();
  return blocks;
}

List<MdSegment> parseMarkdownInline(String text) {
  final segments = <MdSegment>[];
  var last = 0;
  for (final m in _inline.allMatches(text)) {
    if (m.start > last) segments.add(MdSegment('text', text: text.substring(last, m.start)));
    if (m.group(1) != null) {
      segments.add(MdSegment('bold', text: m.group(1)!));
    } else {
      segments.add(MdSegment('ref', ref: int.parse(m.group(2)!)));
    }
    last = m.end;
  }
  if (last < text.length) segments.add(MdSegment('text', text: text.substring(last)));
  return segments;
}
