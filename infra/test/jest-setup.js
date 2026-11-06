// Static AWS credentials, so the SDK's credential chain doesn't try dynamic imports Jest's CJS runner
// can't do (as nakostat). Real calls are intercepted by aws-sdk-client-mock.
process.env.AWS_ACCESS_KEY_ID = 'test';
process.env.AWS_SECRET_ACCESS_KEY = 'test';
process.env.AWS_DEFAULT_REGION = 'eu-west-2';
process.env.AWS_REGION = 'eu-west-2';
