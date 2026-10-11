# Skill分发与调用边界

原仓SKILL.md用于现有本地Skill环境；命令行包负责可独立复现的计算。pip安装不自动注册Skill，薄层也不附带Python运行时或专业引擎。

- Codex现有检查要求name与description，支持metadata与license；不往根部强塞其他平台字段。
- 当前CodeBuddy市场README要求纯数字三段版本。分发适配层使用独立1.0.0版本，不把Python预发布包冒充正式包。
- 市场注册的双语描述、问法、标签放在注册清单；原仓技术版本与市场适配版本各自保留。
- distribution/marketplace-catalog.json登记十二个现有工具。tools/build_marketplace_bundle.py生成独立薄层和注册清单，只做本地打包，不安装或上架。
- 原创程序MIT；第三方原许可及公告、研报、原始响应、数据权限另行保留。薄层不带原始PDF与用户资料。

工作台是可选编排入口，已有专业调用路由，不另建第十三个路由仓。单工具用户按对应仓README安装与准备资料，不必安装工作台。

本地清单字段和包内一致性可验收；没有声称在目标市场导入、检索或托管API调用成功。agent_created的特定版本要求未在当前本机规范找到，不当作所有平台的统一要求。
