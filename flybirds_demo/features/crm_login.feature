# language: zh-CN
功能: CRM 客户关系管理系统 - 登录功能测试

  场景: 验证使用正确的账号密码成功登录 CRM 系统
    # 1. 跳转到登录页面
    假如 跳转页面到[https://demo-console.crmtest.org/login]
    而且 等待[2]秒

    # 2. 输入账号/邮箱（完全匹配官方：在[选择器]中输入[内容]）
    而且 在[input[placeholder*='邮箱']]中输入[forestlin@pmonic.xyz]

    # 3. 输入密码
    而且 在[input[type='password']]中输入[Aa@135246]

    # 4. 点击登录按钮
    而且 点击[text="登录"]
    而且 等待[3]秒

    # 5. 调试停留：保持浏览器打开状态（等待 1 小时）
    而且 等待[10]秒