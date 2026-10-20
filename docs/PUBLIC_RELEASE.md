# 公开发布检查表

此表是每次发布的操作提醒，不是安全认证或永久有效的审计结论。

## 仓库与历史

- [ ] 检查所有准备公开的分支、标签及其完整历史，而不仅是当前文件。
- [ ] 排除环境文件、令牌、私钥、密码哈希、真实健康数据、数据库、导出、日志、备份、镜像和个人部署配置。
- [ ] 检查 README、Issue、PR、附件、Releases、Actions 日志与产物，以及提交作者邮箱。
- [ ] 核对截图使用完全合成数据，且无个人身份、服务器地址或元数据泄露。
- [ ] 如曾泄露凭据，先撤销或轮换；历史清理不能召回别人已保存的副本。

## 代码与文档

- [ ] 确认 MIT LICENSE 和第三方许可义务；WHOOP 品牌及第三方依赖的权利不因本项目许可证而转让。
- [ ] 保留非官方、非医疗诊断声明，以及缺失值、相关性与统计方法的限制。
- [ ] 构建通过，空数据可以启动；检查依赖已知漏洞，记录工具、日期和范围，不能把“未检出”理解为绝对安全。
- [ ] README 与安全说明反映实际实现；计划中的 AI 功能不可描述为已实现。

## 发布与运行服务分离

- [ ] 单独确认 GitHub 仓库是否要切换为 Public；提交这些文档不会自动切换可见性。
- [ ] 个人运行服务仍然受认证或 Tailscale 访问策略保护，不能因源码公开而关闭保护。
- [ ] 检查 GitHub 安全设置中可用的私密漏洞报告、依赖告警和密钥保护功能，按需开启。文档不代表这些设置已启用。
- [ ] 理解公开代码可以被复制与 fork；之后改回私有无法撤回已被保存的副本。

参考：[GitHub 仓库可见性](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)、[移除敏感数据](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)。
