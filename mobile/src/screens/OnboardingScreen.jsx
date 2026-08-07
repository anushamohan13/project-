import React, { useState } from 'react';
import { Alert, ScrollView, Text } from 'react-native';
import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import { api } from '../api/client';
import { useSession } from '../store/SessionContext';
import { spacing } from '../theme/tokens';

export default function OnboardingScreen() {
  const { markProfileReady } = useSession();
  const [username, setUsername] = useState('demo_user');
  const [country, setCountry] = useState('Singapore');
  const [city, setCity] = useState('Singapore');
  const [currency, setCurrency] = useState('SGD');
  const [timezone, setTimezone] = useState('Asia/Singapore');
  const [balance, setBalance] = useState('500');
  const [savings, setSavings] = useState('20');
  const [loading, setLoading] = useState(false);

  async function save() {
    setLoading(true);
    try {
      await api.updateProfile({
        username, country, city, currency, timezone,
        current_balance: balance,
        normal_savings_percent: savings,
        emergency_savings_minimum: '0',
        savings_before_discretionary: true,
        theme_mode: 'system',
      });
      markProfileReady();
    } catch (error) { Alert.alert('Could not save profile', error.message); }
    finally { setLoading(false); }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} keyboardShouldPersistTaps="handled">
      <Text style={{ fontSize: 28, fontWeight: '800', marginBottom: spacing.lg }}>Your planning baseline</Text>
      <FormField label="Username" value={username} onChangeText={setUsername} />
      <FormField label="Country" value={country} onChangeText={setCountry} />
      <FormField label="City" value={city} onChangeText={setCity} />
      <FormField label="Currency" value={currency} onChangeText={setCurrency} />
      <FormField label="Time zone" value={timezone} onChangeText={setTimezone} />
      <FormField label="Current available balance" value={balance} onChangeText={setBalance} keyboardType="decimal-pad" />
      <FormField label="Normal savings target (%)" value={savings} onChangeText={setSavings} keyboardType="decimal-pad" />
      <PrimaryButton title="Save and open dashboard" onPress={save} loading={loading} />
    </ScrollView>
  );
}
