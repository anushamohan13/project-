import React, { useEffect, useState } from 'react';
import { Alert, Platform, ScrollView, Switch, Text, View } from 'react-native';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';

import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import { api } from '../api/client';
import { useSession } from '../store/SessionContext';
import { spacing } from '../theme/tokens';

export default function SettingsScreen() {
  const { logout } = useSession();
  const [preferences, setPreferences] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getNotificationPreferences().then(setPreferences).catch((error) => Alert.alert('Settings error', error.message));
  }, []);

  async function save() {
    setLoading(true);
    try {
      const payload = {
        ...preferences,
        reminder_weekday: Number(preferences.reminder_weekday),
        reminder_hour: Number(preferences.reminder_hour),
        reminder_minute: Number(preferences.reminder_minute),
      };
      delete payload.id;
      setPreferences(await api.updateNotificationPreferences(payload));
      Alert.alert('Saved', 'Notification preferences were updated.');
    } catch (error) { Alert.alert('Could not save settings', error.message); }
    finally { setLoading(false); }
  }

  async function registerPush() {
    if (!Device.isDevice) {
      Alert.alert('Physical device required', 'Expo push tokens are not available in the iOS simulator.');
      return;
    }
    const permission = await Notifications.requestPermissionsAsync();
    if (permission.status !== 'granted') {
      Alert.alert('Permission not granted', 'Enable notifications in iOS Settings to receive reminders.');
      return;
    }
    try {
      const options = process.env.EXPO_PUBLIC_EAS_PROJECT_ID ? { projectId: process.env.EXPO_PUBLIC_EAS_PROJECT_ID } : undefined;
      const result = await Notifications.getExpoPushTokenAsync(options);
      await api.registerPushToken({ token: result.data, platform: Platform.OS });
      Alert.alert('Push enabled', 'This device is registered for budget reminders.');
    } catch (error) { Alert.alert('Could not register push', error.message); }
  }

  if (!preferences) return <View style={{ flex: 1, padding: spacing.lg }}><Text>Loading settings…</Text></View>;

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} keyboardShouldPersistTaps="handled">
      <Text style={{ fontSize: 22, fontWeight: '800', marginBottom: spacing.lg }}>Reminders</Text>
      {[
        ['Email reminders', 'email_enabled'],
        ['Push notifications', 'push_enabled'],
        ['Weekly planning reminder', 'weekly_reminder_enabled'],
      ].map(([label, key]) => (
        <View key={key} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.md }}>
          <Text>{label}</Text>
          <Switch value={Boolean(preferences[key])} onValueChange={(value) => setPreferences((current) => ({ ...current, [key]: value }))} />
        </View>
      ))}
      <FormField label="Reminder weekday (0 Monday – 6 Sunday)" value={String(preferences.reminder_weekday)} onChangeText={(value) => setPreferences((current) => ({ ...current, reminder_weekday: value }))} keyboardType="number-pad" />
      <FormField label="Reminder hour (0–23)" value={String(preferences.reminder_hour)} onChangeText={(value) => setPreferences((current) => ({ ...current, reminder_hour: value }))} keyboardType="number-pad" />
      <FormField label="Time zone" value={preferences.timezone} onChangeText={(value) => setPreferences((current) => ({ ...current, timezone: value }))} />
      <PrimaryButton title="Save reminder settings" onPress={save} loading={loading} />
      <View style={{ height: spacing.sm }} />
      <PrimaryButton title="Register this device for push" onPress={registerPush} />
      <View style={{ height: spacing.sm }} />
      <PrimaryButton title="Queue a test weekly reminder" onPress={() => api.queueWeeklyReminder().then(() => Alert.alert('Queued', 'Email, push, and in-app jobs were queued according to your preferences.')).catch((error) => Alert.alert('Could not queue reminder', error.message))} />
      <Text style={{ fontSize: 22, fontWeight: '800', marginTop: spacing.xl, marginBottom: spacing.md }}>Account</Text>
      <Text style={{ color: '#666', marginBottom: spacing.md }}>OAuth and refresh tokens are stored in Expo SecureStore. Refresh tokens rotate after every use.</Text>
      <PrimaryButton title="Sign out" onPress={logout} />
    </ScrollView>
  );
}
