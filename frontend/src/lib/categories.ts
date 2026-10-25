/**
 * 应用分类的展示名称与排序
 *
 * 应用市场与服务概览共用同一套分类映射，后端只返回分类标识。
 */

export const CATEGORY_LABELS: Record<string, string> = {
  movie: "影视",
  media: "媒体",
  comic: "漫画",
  book: "书籍",
  music: "音乐",
  game: "游戏",
  gallery: "图库",
  news: "资讯",
  download: "下载",
  docker: "Docker",
  tool: "工具",
  network: "网络",
  web: "网站",
  other: "其他",
};

export const CATEGORY_ORDER = [
  "movie",
  "media",
  "comic",
  "book",
  "music",
  "download",
  "gallery",
  "game",
  "news",
  "tool",
  "network",
  "web",
  "docker",
  "other",
];

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}
