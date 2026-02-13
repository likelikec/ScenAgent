import { Box, Image, Center, Stack } from '@mantine/core';

interface DeviceEmulatorProps {
  screenshotUrl?: string;
}

export function DeviceEmulator({ screenshotUrl }: DeviceEmulatorProps) {
  return (
    <Center h="100%" style={{ perspective: '1000px', paddingBottom: 40 }}>
      <Stack align="center" gap={0} style={{ position: 'relative' }}>
        <Box
          w={280}
          h={590} // Scaled down from 360/760
          bg="black"
          style={{
            borderRadius: 32,
            border: '10px solid #222',
            boxShadow: '0 20px 40px -10px rgba(0, 0, 0, 0.5)',
            position: 'relative',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 2
          }}
        >
          {/* Top Bezel / Camera */}
          <Box 
            h={24} 
            bg="black" 
            w="100%" 
            style={{ 
              position: 'absolute', 
              top: 0, 
              zIndex: 10,
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center'
            }} 
          >
               {/* Camera hole */}
               <Box w={8} h={8} bg="#111" style={{ borderRadius: '50%' }} />
          </Box>

          {/* Screen Content */}
          <Box w="100%" h="100%" bg="#050505" style={{ position: 'relative', flex: 1 }}>
            <Image
              src={screenshotUrl || '/device_charging.png'}
              w="100%"
              h="100%"
              fit="contain"
              alt="Device Screen"
              style={{ objectFit: 'contain' }}
            />
          </Box>
          
          {/* Bottom Bezel / Home Indicator */}
          <Box 
              h={16}
              w="100%"
              bg="black"
              style={{ position: 'absolute', bottom: 0, zIndex: 10 }}
          >
              <Box 
              style={{
                  position: 'absolute',
                  bottom: 6,
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: 80,
                  height: 3,
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  borderRadius: 2
              }}
              />
          </Box>
        </Box>

        {/* Charging Cable Connector */}
        <Box
          w={40}
          h={15}
          bg="#333"
          style={{
            borderRadius: '0 0 6px 6px',
            border: '1px solid #444',
            marginTop: -2,
            zIndex: 1,
            boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.5)'
          }}
        />
        {/* Cable Line */}
        <Box
          w={6}
          h={60}
          style={{
            background: 'linear-gradient(to bottom, #333, #222)',
            borderRadius: 3,
            marginTop: 0,
            zIndex: 0,
            boxShadow: '2px 0 5px rgba(0,0,0,0.2)'
          }}
        />
      </Stack>
    </Center>
  );
}
