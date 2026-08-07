import React, { useCallback, useState } from 'react';
import { Alert, RefreshControl, ScrollView, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { api } from '../api/client';
import DoughnutChart from '../components/DoughnutChart';
import PrimaryButton from '../components/PrimaryButton';
import { spacing } from '../theme/tokens';

export default function DashboardScreen({ navigation }) {
  const [plan, setPlan] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try { setPlan(await api.latestBudget()); }
    catch { setPlan(null); }
    finally { setRefreshing(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={load} />}>
      {plan ? (
        <>
          <Text style={{ fontSize: 16, color: '#666', marginBottom: spacing.md }}>Confirmed plan · Version {plan.version}</Text>
          <DoughnutChart allocations={plan.allocations} currency={plan.currency} />
          <View style={{ marginTop: spacing.md }}><PrimaryButton title="Compare plan history" onPress={() => navigation.navigate('PlanHistory')} /></View>
          {Number(plan.overspending_amount) > 0 && <Text style={{ color: '#FF453A', fontWeight: '700' }}>Overspending: {plan.currency} {plan.overspending_amount}</Text>}
        </>
      ) : (
        <View style={{ paddingVertical: 80 }}>
          <Text style={{ fontSize: 28, fontWeight: '800', marginBottom: spacing.md }}>No confirmed plan yet</Text>
          <Text style={{ fontSize: 17, color: '#666', marginBottom: spacing.lg }}>Add income and activities in Planner, calculate the week, and confirm the result.</Text>
          <PrimaryButton title="Refresh dashboard" onPress={load} loading={refreshing} />
        </View>
      )}
    </ScrollView>
  );
}
