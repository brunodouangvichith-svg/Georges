/// Miroir de `api/schemas.py:NewsItemOut`.
class NewsItem {
  final String title;
  final String sourceName;
  final DateTime? publishedAt;
  final String? url;

  NewsItem({required this.title, required this.sourceName, this.publishedAt, this.url});

  factory NewsItem.fromJson(Map<String, dynamic> json) => NewsItem(
        title: json['title'] as String,
        sourceName: json['source_name'] as String,
        publishedAt: json['published_at'] != null ? DateTime.parse(json['published_at'] as String) : null,
        url: json['url'] as String?,
      );
}
