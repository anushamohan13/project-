import { requireNativeModule } from 'expo-modules-core';

const nativeModule = requireNativeModule('BudgetWidget');

export async function writeBudgetWidgetSnapshot(snapshot) {
  return nativeModule.writeSnapshot(snapshot);
}

export async function clearBudgetWidgetSnapshot() {
  return nativeModule.clearSnapshot();
}

export function getBudgetWidgetLastWrittenAt() {
  return nativeModule.lastWrittenAt();
}
