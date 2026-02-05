TorchTracker - 토치라이트 인피니트 트래커
==========================================

처음 설치 시
------------
ZIP 파일로 다운로드한 경우, 실행 전에 "차단 해제"가 필요할 수 있습니다:

1. 다운로드한 ZIP 파일을 우클릭 (압축 풀기 전에!)
2. "속성" 클릭
3. 하단의 "차단 해제" 체크
4. "확인" 클릭
5. ZIP 압축을 풀고 TorchTracker.exe 실행

필수 요구사항
-------------
TorchTracker는 기본적으로 네이티브 창 모드로 실행됩니다.

필요한 런타임:
- Windows 10 또는 11
- WebView2 Runtime (Windows 11과 최신 Windows 10에는 기본 설치됨)
- .NET 8 Desktop Runtime (네이티브 창 모드에 필요)

앱이 브라우저로 열리는 경우:
1. 먼저 WebView2 Runtime 설치:
   https://go.microsoft.com/fwlink/p/?LinkId=2124703

2. 그래도 안 되면 .NET 8 Desktop Runtime (x64) 설치:
   https://dotnet.microsoft.com/ko-kr/download/dotnet/8.0
   → ".NET Desktop Runtime x64" 다운로드

브라우저 모드 (대체 방법)
------------------------
네이티브 창 모드가 작동하지 않는 경우, 브라우저 모드로 실행할 수 있습니다:

1. TorchTracker 폴더에서 명령 프롬프트 열기
2. 실행: TorchTracker.exe serve --no-window
3. 기본 브라우저에서 대시보드가 열립니다

바로가기 만들기:
- TorchTracker.exe 우클릭 → 바로가기 만들기
- 바로가기 우클릭 → 속성
- "대상"에 추가: serve --no-window
- 예: "C:\TorchTracker\TorchTracker.exe" serve --no-window

사용 방법
---------
1. TorchTracker.exe 실행
2. 메시지가 나오면 토치라이트 인피니트 게임 폴더 선택
3. 토치라이트 인피니트에서 설정 → "로그 활성화" 클릭
4. 캐릭터 선택 화면으로 로그아웃 후 다시 로그인
   중요: 게임을 끄지 말고 로그아웃만 하세요!
5. TorchTracker가 캐릭터를 감지하고 루팅 추적을 시작합니다

기존 인벤토리를 동기화하려면 인게임 가방을 열고
정렬 버튼을 클릭하세요 - TorchTracker가 현재 아이템을 업데이트합니다.

문제 해결
---------
Q: 앱이 브라우저로 열려요
A: .NET 8 Desktop Runtime (x64)를 설치하세요
   https://dotnet.microsoft.com/ko-kr/download/dotnet/8.0

Q: 창이 비어있거나 로딩이 안 돼요
A: WebView2 Runtime을 설치하세요
   https://go.microsoft.com/fwlink/p/?LinkId=2124703

Q: 로그가 감지되지 않아요
A: 게임 설정에서 "로그 활성화"를 켜고, 게임을 끄지 말고
   캐릭터 선택 화면으로 로그아웃 후 다시 로그인하세요

추가 정보
---------
GitHub: https://github.com/oovbeats-cpu/TorchTrackerForKorean
