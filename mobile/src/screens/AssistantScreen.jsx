import React, { useState } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';

import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import { api } from '../api/client';
import { spacing } from '../theme/tokens';
import { syncWidgetSnapshot } from '../services/widgetSnapshot';

function ProposalCard({ proposal, onConfirm, onReject, onReverse, onRecalculate, busy }) {
  const before = Object.fromEntries((proposal.before_allocations || []).map((item) => [item.category, Number(item.amount)]));
  const changes = (proposal.proposed_allocations || [])
    .map((item) => ({ ...item, difference: Number(item.amount) - (before[item.category] || 0) }))
    .filter((item) => Math.abs(item.difference) > 0.001);

  return (
    <View style={{ padding: spacing.md, borderRadius: 18, backgroundColor: 'rgba(255,159,10,0.14)', marginBottom: spacing.md }}>
      <Text style={{ fontSize: 18, fontWeight: '800' }}>Change requires confirmation</Text>
      <Text style={{ color: '#666', marginVertical: spacing.sm }}>Status: {proposal.status}</Text>
      {changes.map((item) => (
        <Text key={item.category}>{item.category}: {item.difference >= 0 ? '+' : ''}{item.difference.toFixed(2)}</Text>
      ))}
      {proposal.financial_impact?.shortfall !== undefined && (
        <Text style={{ marginTop: spacing.sm, fontWeight: '700' }}>Shortfall: {proposal.financial_impact.shortfall}</Text>
      )}
      {proposal.status === 'awaiting_confirmation' && (
        <>
          <View style={{ height: spacing.sm }} />
          <PrimaryButton title="Confirm change" onPress={onConfirm} loading={busy} />
          <View style={{ height: spacing.sm }} />
          <PrimaryButton title="Recalculate from latest plan" onPress={onRecalculate} disabled={busy} />
          <View style={{ height: spacing.sm }} />
          <PrimaryButton title="Reject proposal" onPress={onReject} disabled={busy} />
        </>
      )}
      {proposal.status === 'applied' && (
        <>
          <View style={{ height: spacing.sm }} />
          <PrimaryButton title="Undo this AI change" onPress={onReverse} loading={busy} />
        </>
      )}
    </View>
  );
}

export default function AssistantScreen() {
  const [message, setMessage] = useState('Can I afford a laptop costing SGD 1,500?');
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [proposal, setProposal] = useState(null);
  const [loading, setLoading] = useState(false);

  async function ensureConversation() {
    if (conversationId) return conversationId;
    const conversation = await api.createConversation({ title: 'Financial planning session', mode: 'action' });
    setConversationId(conversation.id);
    return conversation.id;
  }

  async function send() {
    const outgoing = message.trim();
    if (!outgoing) return;
    setLoading(true);
    try {
      const id = await ensureConversation();
      const response = await api.sendConversationMessage(id, outgoing, 'action');
      setMessages((current) => [...current, { role: 'user', text: outgoing }, { role: 'assistant', text: response.answer }]);
      if (response.proposal_id) setProposal(await api.getProposal(response.proposal_id));
      setMessage('');
    } catch (error) { Alert.alert('Assistant error', error.message); }
    finally { setLoading(false); }
  }

  async function confirm() {
    setLoading(true);
    try {
      const result = await api.confirmProposal(proposal.id);
      setProposal(result.proposal);
      const snapshot = await api.widgetSnapshot();
      await syncWidgetSnapshot(snapshot);
      Alert.alert('Change applied', `Budget plan version ${result.plan.version} was created.`);
    } catch (error) { Alert.alert('Could not apply change', error.message); }
    finally { setLoading(false); }
  }

  async function reject() {
    setLoading(true);
    try { setProposal(await api.rejectProposal(proposal.id)); }
    catch (error) { Alert.alert('Could not reject proposal', error.message); }
    finally { setLoading(false); }
  }

  async function reverse() {
    setLoading(true);
    try {
      const result = await api.reverseProposal(proposal.id);
      setProposal(result.proposal);
      const snapshot = await api.widgetSnapshot();
      await syncWidgetSnapshot(snapshot);
      Alert.alert('Change reversed', `Restored as new plan version ${result.plan.version}.`);
    } catch (error) { Alert.alert('Could not reverse change', error.message); }
    finally { setLoading(false); }
  }

  async function recalculate() {
    setLoading(true);
    try {
      const response = await api.recalculateProposal(proposal.id);
      setMessages((current) => [...current, { role: 'assistant', text: response.answer }]);
      setProposal(await api.getProposal(response.proposal_id));
    } catch (error) { Alert.alert('Could not recalculate', error.message); }
    finally { setLoading(false); }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} keyboardShouldPersistTaps="handled">
      <Text style={{ color: '#666', marginBottom: spacing.lg }}>The model selects an allowlisted tool. Python performs the calculation. Saved plans only change after explicit confirmation.</Text>
      {messages.map((item, index) => (
        <View key={`${item.role}-${index}`} style={{ alignSelf: item.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '90%', padding: spacing.md, borderRadius: 18, backgroundColor: item.role === 'user' ? '#0A84FF' : 'rgba(142,142,147,0.18)', marginBottom: spacing.sm }}>
          <Text style={{ color: item.role === 'user' ? 'white' : undefined }}>{item.text}</Text>
        </View>
      ))}
      {proposal && (
        <ProposalCard proposal={proposal} onConfirm={confirm} onReject={reject} onReverse={reverse} onRecalculate={recalculate} busy={loading} />
      )}
      <FormField label="Ask PocketPilot" value={message} onChangeText={setMessage} placeholder="Move SGD 100 from shopping to savings" />
      <PrimaryButton title="Send" onPress={send} loading={loading} disabled={!message.trim()} />
    </ScrollView>
  );
}
