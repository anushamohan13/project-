import { Platform } from 'react-native';

export async function syncWidgetSnapshot(snapshot) {
  if (Platform.OS !== 'ios') return false;
  try {
    const module = await import('budget-widget');
    await module.writeBudgetWidgetSnapshot(snapshot);
    return true;
  } catch (error) {
    // Expo Go cannot load custom native modules. Use an EAS development build
    // or `npx expo run:ios` after adding the WidgetKit extension in Xcode.
    console.warn('Widget snapshot was not written:', error.message);
    return false;
  }
}

export async function clearWidgetSnapshot() {
  if (Platform.OS !== 'ios') return;
  try {
    const module = await import('budget-widget');
    await module.clearBudgetWidgetSnapshot();
  } catch (error) {
    console.warn('Widget snapshot was not cleared:', error.message);
  }
}
