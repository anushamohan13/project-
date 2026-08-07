const { withEntitlementsPlist, withInfoPlist } = require('@expo/config-plugins');

const APP_GROUP = process.env.EXPO_PUBLIC_APP_GROUP_ID || 'group.com.example.pocketpilot';

module.exports = function withBudgetWidget(config) {
  config = withEntitlementsPlist(config, (configuration) => {
    const existing = configuration.modResults['com.apple.security.application-groups'] || [];
    configuration.modResults['com.apple.security.application-groups'] = Array.from(new Set([...existing, APP_GROUP]));
    return configuration;
  });
  config = withInfoPlist(config, (configuration) => {
    configuration.modResults.PocketPilotAppGroup = APP_GROUP;
    return configuration;
  });
  return config;
};
