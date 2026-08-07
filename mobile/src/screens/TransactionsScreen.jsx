import React, { useCallback, useState } from 'react';
import { Alert, RefreshControl, ScrollView, Switch, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';

import { api } from '../api/client';
import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import { spacing } from '../theme/tokens';

export default function TransactionsScreen({ navigation }) {
  const [merchant, setMerchant] = useState('Supermarket');
  const [amount, setAmount] = useState('42.50');
  const [category, setCategory] = useState('Groceries');
  const [online, setOnline] = useState(false);
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [transactions, totals] = await Promise.all([api.listTransactions(), api.transactionSummary()]);
      setItems(transactions);
      setSummary(totals);
    } catch (error) { Alert.alert('Could not load transactions', error.message); }
    finally { setLoading(false); }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function add() {
    setLoading(true);
    try {
      await api.createTransaction({
        merchant,
        amount,
        currency: 'SGD',
        occurred_at: new Date().toISOString(),
        category,
        payment_method: 'Card',
        is_online: online,
        kind: 'expense',
        related_activity_id: null,
        receipt_image_url: null,
        notes: null,
      });
      await load();
    } catch (error) { Alert.alert('Could not add transaction', error.message); }
    finally { setLoading(false); }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />} keyboardShouldPersistTaps="handled">
      {summary && (
        <View style={{ padding: spacing.md, borderRadius: 18, backgroundColor: 'rgba(142,142,147,0.12)', marginBottom: spacing.lg }}>
          <Text style={{ fontSize: 22, fontWeight: '800' }}>{summary.currency} {Number(summary.total_expenses).toFixed(2)}</Text>
          <Text>Total expenses · {summary.transaction_count} transactions</Text>
          <Text>Online shopping: {summary.currency} {Number(summary.online_spending).toFixed(2)}</Text>
        </View>
      )}
      <FormField label="Merchant" value={merchant} onChangeText={setMerchant} />
      <FormField label="Amount" value={amount} onChangeText={setAmount} keyboardType="decimal-pad" />
      <FormField label="Category" value={category} onChangeText={setCategory} />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.md }}>
        <Text>Online purchase</Text>
        <Switch value={online} onValueChange={setOnline} />
      </View>
      <PrimaryButton title="Add transaction" onPress={add} loading={loading} />
      <View style={{ height: spacing.sm }} />
      <PrimaryButton title="Manage custom categories" onPress={() => navigation.navigate('Categories')} />

      <Text style={{ fontSize: 22, fontWeight: '800', marginTop: spacing.xl, marginBottom: spacing.md }}>Recent transactions</Text>
      {items.map((item) => (
        <View key={item.id} style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: spacing.md, borderBottomWidth: 0.5, borderBottomColor: 'rgba(142,142,147,0.35)' }}>
          <View>
            <Text style={{ fontWeight: '700' }}>{item.merchant}</Text>
            <Text style={{ color: '#666' }}>{item.category} · {item.is_online ? 'Online' : 'In store'}</Text>
          </View>
          <Text style={{ fontWeight: '700' }}>−{item.currency} {Number(item.amount).toFixed(2)}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
