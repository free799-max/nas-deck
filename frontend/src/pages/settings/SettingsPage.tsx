/**
 * 系统设置页面
 *
 * 使用 Tabs 组织各类配置：基础配置、存储配置。
 */

import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { BasicSettingsTab } from "./BasicSettingsTab";
import { StorageSettingsTab } from "./StorageSettingsTab";
import { SlidersHorizontal, HardDrive } from "lucide-react";

export function SettingsPage() {
  return (
    <div className="w-full space-y-6">
      <Tabs defaultValue="basic" className="w-full">
        <TabsList>
          <TabsTrigger value="basic">
            <SlidersHorizontal className="h-4 w-4" />
            基础配置
          </TabsTrigger>
          <TabsTrigger value="storage">
            <HardDrive className="h-4 w-4" />
            存储配置
          </TabsTrigger>
        </TabsList>

        <TabsContent value="basic" className="mt-4">
          <BasicSettingsTab />
        </TabsContent>

        <TabsContent value="storage" className="mt-4">
          <StorageSettingsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
