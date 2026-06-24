/**
 * 系统设置页面
 *
 * 使用 Tabs 组织各类配置，当前仅实现「基础配置」Tab。
 */

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { BasicSettingsTab } from "./BasicSettingsTab";

export function SettingsPage() {
  return (
    <div className="space-y-6">
      <Tabs defaultValue="basic" className="w-full">
        <TabsList>
          <TabsTrigger value="basic">基础配置</TabsTrigger>
        </TabsList>

        <TabsContent value="basic" className="mt-4">
          <BasicSettingsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
