/**
 * 自动化分类入口页面
 *
 * 展示影视、漫画、书籍等媒体类型分类卡片。
 */

import { Card, CardContent } from "@/components/ui/card";
import {
  Film,
  BookImage,
  BookOpen,
  Music,
  Gamepad2,
  Images,
  Newspaper,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";

interface AutomationCategory {
  key: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

const CATEGORIES: AutomationCategory[] = [
  { key: "media", label: "影视", icon: Film, description: "电影、剧集、综艺自动化下载与管理" },
  { key: "comics", label: "漫画", icon: BookImage, description: "漫画资源抓取与阅读管理" },
  { key: "books", label: "书籍", icon: BookOpen, description: "电子书自动下载与书库管理" },
  { key: "music", label: "音乐", icon: Music, description: "音乐资源整理与流媒体播放" },
  { key: "games", label: "游戏", icon: Gamepad2, description: "游戏相关服务与资源管理" },
  { key: "gallery", label: "图库", icon: Images, description: "照片、图片资源管理与展示" },
  { key: "news", label: "资讯", icon: Newspaper, description: "RSS、资讯聚合与归档" },
];

export function AutomationCategoriesPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-foreground">自动化</h1>
        <p className="text-sm text-muted-foreground mt-1">
          按媒体类型选择应用组合，一键部署自动化服务栈
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {CATEGORIES.map((category) => {
          const Icon = category.icon;
          return (
            <Link key={category.key} to={`/automation/${category.key}`}>
              <Card className="rounded-xl p-5 border border-border/80 shadow-sm hover:shadow-[0_4px_14px_rgba(0,0,0,0.08)] hover:border-border transition-all cursor-pointer h-full">
                <CardContent className="p-0 flex items-center gap-4">
                  <div className="h-14 w-14 rounded-xl bg-primary/5 flex items-center justify-center shrink-0">
                    <Icon className="h-7 w-7 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold text-foreground">
                      {category.label}
                    </h3>
                    <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                      {category.description}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
