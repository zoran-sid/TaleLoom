// 文字版界面测试的共用操作。

/** 存读档控件收在“存档”菜单里；操作前先确保菜单已展开。 */
export async function openSaves(page) {
  const menu = page.locator('#save-menu');
  if (await menu.getAttribute('open') === null) await menu.locator('summary').click();
}
