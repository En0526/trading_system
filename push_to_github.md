# 把專案推上 GitHub（你只需要做這幾步）

## 步驟 1：設定 Git 身份（只需做一次）

在 PowerShell 或 CMD 裡執行（**請改成你的名字和 Email**）：

```powershell
git config --global user.email "你的Email@example.com"
git config --global user.name "你的名字或 GitHub 帳號"
```

例如：
```powershell
git config --global user.email "abc@gmail.com"
git config --global user.name "Ennn0526"
```

---

## 步驟 2：建立第一次 commit（本機已完成 add，只差 commit）

在專案目錄 `C:\trading_system` 執行：

```powershell
cd C:\trading_system
git commit -m "Initial commit: trading system"
```

---

## 步驟 3：在 GitHub 建立新倉庫

1. 打開瀏覽器，登入 [GitHub](https://github.com/)
2. 點右上角 **+** → **New repository**
3. **Repository name** 填：`trading_system`（或你喜歡的名稱）
4. **不要**勾選 "Add a README file"
5. 點 **Create repository**
6. 建立後會看到倉庫網址，例如：`https://github.com/Ennn0526/trading_system.git`（把 `Ennn0526` 換成你的帳號）

---

## 步驟 4：連到 GitHub 並推送

**把下面網址換成你在步驟 3 看到的倉庫網址**，在 PowerShell 執行：

```powershell
cd C:\trading_system
git branch -M main
git remote add origin https://github.com/你的帳號/trading_system.git
git push -u origin main
```

例如你的 GitHub 帳號是 `Ennn0526`，就執行：

```powershell
git remote add origin https://github.com/Ennn0526/trading_system.git
git push -u origin main
```

若 GitHub 要求登入，可用：
- 帳號 + **Personal Access Token**（不要用密碼）  
- 或 GitHub Desktop / 其他 Git 客戶端登入

建立 Token：GitHub 右上角頭像 → **Settings** → **Developer settings** → **Personal access tokens** → **Generate new token**，勾選 `repo` 權限。

---

完成後，到 GitHub 網頁重新整理，就會看到專案已經上傳。
