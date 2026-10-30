# language: zh-CN
功能: WeTrade App - 客户修改邮箱并保存

  场景: 客户在「我的-个人信息」把邮箱修改为 potato@qq.com 后保存成功
    # 0. 清空 App 数据，保证从登录页开始（登录态会缓存，已登录时没有登录入口）
    假如 清除应用数据[com.wetrade.crm.trial]

    # 1. 启动 App 并登录：App 端客户账号，与 Web 后台账号不同
    当 启动应用[com.wetrade.crm.trial][com.wetrade.crm.MainActivity]
    而且 页面渲染完成出现元素[name=登录/注册]
    而且 点击[name=登录/注册]
    而且 页面渲染完成出现元素[text=请输入邮箱或手机号]
    而且 在[text=请输入邮箱或手机号]中输入[test_potato001@test.com]
    而且 在[text=请输入密码]中输入[aa111111]
    而且 点击[name=登录]
    而且 等待[10]秒

    # 2. 进入「我的 - 个人信息」
    而且 按文案点击[第 5 个标签]
    而且 等待[2]秒
    而且 按文案点击[个人信息]
    而且 页面应包含文案[社交账号]

    # 3. 打开邮箱编辑弹窗，清空后改为 potato@qq.com
    而且 按文案点击[邮箱]
    而且 清空输入框
    而且 在输入框输入[potato@qq.com]
    而且 按文案点击[确认]

    # 4. 预期保存成功：个人信息页展示新邮箱
    而且 页面应包含文案[potato@qq.com]
