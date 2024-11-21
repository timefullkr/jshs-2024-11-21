// WebSocket.js
let socket; // WebSocket 객체를 전역 변수로 선언
let reconnectInterval = 5000; // 초기 재접속 시도 간격 (밀리초)

$(document).ready(function() {
    // 웹소켓 연결 초기화
    socket = connectWebSocket();
    
    // 페이지를 떠날 때 WebSocket 연결을 종료
    $(window).on('beforeunload', function() {
        if (socket) {
            socket.close();
        }
    });
});

/**
 * WebSocket을 초기화하고 관리하는 함수
 * @returns {WebSocket} 생성된 WebSocket 객체
 */
function connectWebSocket() {
    // 이미 연결되어 있거나 연결 중인 경우 재접속 시도하지 않음
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        console.log('이미 WebSocket이 연결되었거나 연결 중입니다.');
        return socket;
    }

    // localStorage에서 client_id 가져오기
    let clientId = localStorage.getItem('client_id');
    if (!clientId) {
        // 새로운 client_id 생성
        clientId = generateUUID();
        // localStorage에 client_id 저장
        localStorage.setItem('client_id', clientId);
    }

    // HTTPS 여부에 따라 적절한 WebSocket 프로토콜(wss/ws) 선택
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socketUrl = `${protocol}://${window.location.host}/ws?client_id=${clientId}`;

    // WebSocket 객체 생성 및 연결
    socket = new WebSocket(socketUrl);
    
    // WebSocket이 연결되었을 때 실행되는 콜백
    socket.onopen = function() {
        console.log('WebSocket 연결됨');
        // 연결이 성공하면 재접속 간격 초기화
        reconnectInterval = 5000;
    };

    // WebSocket 에러 처리 핸들러
    socket.onerror = function(error) {
        console.error('WebSocket 에러 발생:', error);
        // 사용자에게 에러 알림 (선택 사항)
        alert('실시간 연결에 문제가 발생했습니다. 잠시 후 다시 시도해주세요.');
    };

    // 서버로부터 메시지를 받았을 때 실행되는 핸들러
    socket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('메시지 처리 중 에러 발생:', error);
        }
    };

    // WebSocket 연결이 종료되었을 때 실행되는 핸들러
    socket.onclose = function() {
        console.log('WebSocket 연결 종료. 재접속 시도...');
        setTimeout(() => {
            // 재접속 시도 전에 재접속 간격을 지수 백오프 방식으로 증가
            reconnectInterval = Math.min(reconnectInterval * 2, 60000); // 최대 60초
            connectWebSocket();
        }, reconnectInterval);
    };

    return socket;
}

function generateUUID() {
    // UUID 생성 (보안 강화된 방식)
    return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, function(c) {
        return (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16);
    });
}

/**
 * WebSocket으로부터 받은 메시지를 처리하는 함수
 * @param {Object} data - 서버로부터 받은 데이터 객체
 */
function handleWebSocketMessage(data) {
    switch(data.type) {
        case 'connection_count':
            // 접속자 수 업데이트 UI 처리
            $('#connection-count').text(data.count);
            break;
        case 'reaction':
            // 좋아요 수 업데이트 UI 처리
            const card = $(`#school-${data.school_code}`);
            update_count_ReactionUI(card, data.likes);
            break;
        default:
            console.warn('알 수 없는 메시지 타입:', data.type);
    }
}


