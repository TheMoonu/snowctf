# SNOWCTF_V1.0(个人版)
一个基于django开发的CTF竞赛平台。
整合了贴合中文操作逻辑的CTF竞赛系统、知识竞赛系统、漏洞靶场练习系统、WIKI知识库管理系统、工具管理及招聘岗位发布等核心功能模块，全面覆盖竞赛组织、技能实训、知识沉淀、资源管理与人才对接等多元需求。您的支持就是我们技术开源的动力！谢谢！

目标：致力于共创、共享网络安全学习环境。

后端：Python3.11+Django5.

前端：Bootstrap

安装及使用指导：目前CTF竞赛功能点star可免费安装，请进517929458了解如何安装最新版！开源代码未更新！

页面UI具体参考：[SECSNOW_V1.0](https://www.secsnow.cn/)


交流、学习、合作、专业版免费试用联系：qun：扣扣学习交流群517929458、邮箱：flechazo890@gmail.com




## 动态分数算法
比赛分数会根据解题次数动态调整，跟解题快慢无关

![分数](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/img20250228171202.png)

```python
points = max(
    minimum_points, 
    initial_points * (3 + min(solve_count, 1)) / (3 + solve_count)
)
```

## 界面介绍

#### 数据大屏
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/数据大屏.png)

#### 比赛列表

![主页面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/比赛列表.png)


#### 题目界面
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/比赛答题页面.png)

#### 答题界面
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/容器下方打码.png)

#### 自动化报名
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/报名系统.png)

#### 解题动态
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/解题动态.png)

#### 前台比赛管理
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/前台比赛管理.png)

#### 报名信息
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/报名信息.png)

#### 创建题目
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/前台创建题目.png)

#### 简约版比赛界面
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/简约版比赛界面.png)

#### 简约版答题界面
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/简约版答题界面.png)

#### 个人信息页面
![比赛界面](https://cdn.jsdelivr.net/gh/TheMoonu/TheMoonu/个人信息页面.png)




## 其它声明
本项目开发过程中使用了部分[iznoe](https://github.com/Hopetree/izone "iznoe")、[simpleui](https://github.com/newpanjing/simpleui)项目代码及架构，非常感谢！
